import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import os
import matplotlib.pyplot as plt

st.set_page_config(page_title="Plano de Quitação de Dívidas", layout="wide")

# ---------------- Helpers ----------------
def a2m(rate_annual):
    if rate_annual is None or pd.isna(rate_annual):
        return 0.0
    return (1 + float(rate_annual)/100.0)**(1/12) - 1

def load_csv_if_exists(path, dtype=None, parse_dates=None):
    if os.path.exists(path):
        try:
            return pd.read_csv(path, dtype=dtype, parse_dates=parse_dates)
        except Exception:
            return None
    return None

def save_csv(df, path):
    df.to_csv(path, index=False)

def compute_competencia(today: date, base_day: int = 20) -> str:
    y = today.year
    m = today.month
    if today.day < base_day:
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
    return f"{y:04d}-{m:02d}"

# ---------------- Defaults ----------------
DEFAULT_INPC_2025 = 4.7
BASE_DAY = 20
BASE_START = datetime(2025, 9, BASE_DAY)

default_debts = pd.DataFrame([
    {"id":"CX-6481-47","nome":"Consignado Caixa — 03.3395.110.0006481-47","tipo":"Consignado PRICE","saldo_atual":12368.49,"parcela":234.63,"juros_aa":12.55,"indexador":"","spread_aa":0.0,"prioridade":2},
    {"id":"CX-6621-31","nome":"Consignado Caixa — 03.3395.110.0006621-31","tipo":"Consignado PRICE","saldo_atual":12885.31,"parcela":233.96,"juros_aa":12.55,"indexador":"","spread_aa":0.0,"prioridade":3},
    {"id":"CX-2022","nome":"Consignado Caixa — 16.2780.110.0009910-07 (2022)","tipo":"Consignado PRICE","saldo_atual":37301.46,"parcela":601.49,"juros_aa":14.98,"indexador":"","spread_aa":0.0,"prioridade":5},
    {"id":"CX-2025-0117665-68","nome":"Consignado Caixa — 00.0000.000.0117665-68 (2025)","tipo":"Consignado PRICE","saldo_atual":40537.88,"parcela":732.46,"juros_aa":20.98,"indexador":"","spread_aa":0.0,"prioridade":6},
    {"id":"CX-123043-84","nome":"Consignado Caixa — 00.0000.000.0123043-84","tipo":"Consignado PRICE","saldo_atual":33511.77,"parcela":596.89,"juros_aa":20.98,"indexador":"","spread_aa":0.0,"prioridade":4},
    {"id":"FUNCEF-FIXO-300001369416","nome":"FUNCEF — CredPlan Fixo (300001369416)","tipo":"Fixo","saldo_atual":7342.42,"parcela":200.37,"juros_aa":10.58,"indexador":"","spread_aa":0.0,"prioridade":1},
    {"id":"FUNCEF-VAR-300001364505","nome":"FUNCEF — CredPlan Variável (300001364505)","tipo":"INPC + Spread","saldo_atual":81287.58,"parcela":1147.88,"juros_aa":"","indexador":"INPC","spread_aa":6.76,"prioridade":7},
    {"id":"FIES-2015","nome":"FIES","tipo":"Subsidiado","saldo_atual":24855.33,"parcela":308.94,"juros_aa":3.00,"indexador":"","spread_aa":0.0,"prioridade":8},
])

# ---------------- State & Sidebar ----------------
if "dividas_df" not in st.session_state:
    saved = load_csv_if_exists("dividas.csv")
    st.session_state["dividas_df"] = saved if isinstance(saved, pd.DataFrame) else default_debts.copy()

dividas_df = st.session_state["dividas_df"].copy()

st.sidebar.header("Configurações")
inpc_aa = st.sidebar.number_input("INPC anual (%)", min_value=0.0, max_value=25.0, value=DEFAULT_INPC_2025, step=0.1)
horizonte_meses = st.sidebar.slider("Horizonte (meses)", min_value=12, max_value=180, value=120, step=12)

st.sidebar.write("—")
st.sidebar.subheader("Salvar/Carregar Dados")
if st.sidebar.button("Salvar dívidas"):
    try:
        # salva o que está na UI (editado), não o snapshot antigo
        save_csv(st.session_state.get("dividas_edit", dividas_df), "dividas.csv")
        st.session_state["dividas_df"] = st.session_state.get("dividas_edit", dividas_df).copy()
        st.sidebar.success("Dívidas salvas em dividas.csv")
    except Exception as e:
        st.sidebar.error(f"Erro ao salvar dívidas: {e}")

uploaded = st.sidebar.file_uploader("Carregar dívidas (CSV)", type=["csv"])
if uploaded is not None:
    try:
        new_df = pd.read_csv(uploaded)
        st.session_state["dividas_df"] = new_df
        dividas_df = new_df.copy()
        st.sidebar.success("Dívidas carregadas.")
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar CSV: {e}")

st.title("🔁 Simulador de Quitação de Dívidas (Avalanche do Orçamento)")
st.caption("Edite os valores, defina aportes variáveis e acompanhe o checklist mensal. Base: dia 20 de cada mês.")

# ---------------- 1) Editor de Dívidas ----------------
st.markdown("### 1) Edite suas dívidas (valores atuais)")
dividas_edit = st.data_editor(
    dividas_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "juros_aa": st.column_config.NumberColumn("juros_aa (%)", format="%.2f"),
        "spread_aa": st.column_config.NumberColumn("spread_aa (%)", format="%.2f"),
        "saldo_atual": st.column_config.NumberColumn("saldo_atual (R$)", format="%.2f"),
        "parcela": st.column_config.NumberColumn("parcela (R$)", format="%.2f"),
        "prioridade": st.column_config.NumberColumn("prioridade (ordem)"),
    },
    hide_index=True
)
st.session_state["dividas_edit"] = dividas_edit.copy()

# ---------------- 2) Aportes mensais ----------------
st.markdown("### 2) Aportes mensais (editáveis e salváveis)")
if "aportes_df" not in st.session_state:
    ap_saved = load_csv_if_exists("aportes.csv")
    if isinstance(ap_saved, pd.DataFrame) and "mes" in ap_saved.columns and "aporte" in ap_saved.columns:
        st.session_state["aportes_df"] = ap_saved
    else:
        st.session_state["aportes_df"] = pd.DataFrame({"mes": list(range(1, 25)), "aporte": [1500.0]*24})

aportes_df = st.session_state["aportes_df"].copy()

col_a, col_b = st.columns([1,1])
with col_a:
    aporte_default = st.number_input("Preencher/Atualizar aporte padrão (R$)", min_value=0.0, value=1500.0, step=100.0)
with col_b:
    meses_novos = st.number_input("Meses futuros a adicionar", min_value=0, max_value=180, value=0, step=12)

c1, c2, c3 = st.columns([1,1,1])
with c1:
    if st.button("Aplicar valor padrão aos meses existentes"):
        aportes_df["aporte"] = float(aporte_default)
        st.session_state["aportes_df"] = aportes_df.copy()  # <-- Adicione esta linha
with c2:
    if st.button("Adicionar meses futuros"):
        if meses_novos > 0:
            start = 1 if aportes_df.empty else int(aportes_df["mes"].max())+1
            extra = pd.DataFrame({"mes": list(range(start, start+int(meses_novos))), "aporte": [float(aporte_default)]*int(meses_novos)})
            aportes_df = pd.concat([aportes_df, extra], ignore_index=True)
            st.session_state["aportes_df"] = aportes_df.copy()  # <-- Adicione esta linha
with c3:
    if st.button("Salvar aportes"):
        try:
            save_csv(aportes_df, "aportes.csv")
            st.session_state["aportes_df"] = aportes_df.copy()
            st.success("Aportes salvos em aportes.csv")
        except Exception as e:
            st.error(f"Erro ao salvar aportes: {e}")

# ---------------- 3) Simulação principal ----------------
st.markdown("### 3) Rodar simulação")
st.write("Método **Avalanche do Orçamento**: quita primeiro pela **prioridade**, realocando as parcelas liberadas para acelerar as próximas.")

def prepare_debts(df, inpc_aa):
    rows = []
    for _, r in df.iterrows():
        if r["tipo"] == "INPC + Spread":
            annual_rate = (inpc_aa or 0.0) + float(r.get("spread_aa", 0.0) or 0.0)
        else:
            annual_rate = float(r.get("juros_aa") or 0.0)
        rows.append({
            "id": r["id"],
            "nome": r["nome"],
            "tipo": r["tipo"],
            "saldo": float(r["saldo_atual"] or 0.0),
            "parcela": float(r["parcela"] or 0.0),
            "rate_m": a2m(annual_rate),
            "prioridade": int(r["prioridade"] or 999),
        })
    debts = pd.DataFrame(rows)
    debts = debts.sort_values(by=["prioridade", "saldo"]).reset_index(drop=True)
    return debts

def simulate(debts_df, aportes_df, months, base_date):
    debts = debts_df.copy()
    aportes = aportes_df.set_index("mes")["aporte"].to_dict()
    records = []
    payoff = {row["id"]: pd.NaT for _, row in debts.iterrows()}  # Initialize with NaT (Not a Timestamp)
    snowball_extra = 0.0
    for m in range(1, months+1):
        date = pd.Timestamp(base_date) + pd.DateOffset(months=m-1)
        min_pay_total = 0.0
        interest_this_month = 0.0

        for idx in debts.index:
            if debts.at[idx, "saldo"] <= 0.0:
                continue
            saldo0 = debts.at[idx, "saldo"]
            rate_m = debts.at[idx, "rate_m"]
            parcela = debts.at[idx, "parcela"]
            saldo1 = saldo0 * (1.0 + rate_m)
            interest_this_month += saldo0 * rate_m
            pago = min(parcela, saldo1)
            saldo2 = max(0.0, saldo1 - pago)
            min_pay_total += pago
            debts.at[idx, "saldo"] = saldo2

        aporte = float(aportes.get(m, 0.0) or 0.0) + snowball_extra
        extra_used = 0.0
        for idx in debts.index:
            if aporte <= 0.0:
                break
            if debts.at[idx, "saldo"] <= 0.0:
                continue
            saldo = debts.at[idx, "saldo"]
            pago = min(aporte, saldo)
            saldo -= pago
            aporte -= pago
            extra_used += pago
            debts.at[idx, "saldo"] = saldo

        newly_freed = 0.0
        for idx in debts.index:
            if debts.at[idx, "saldo"] <= 0.0 and payoff[debts.at[idx, "id"]] is None:
                payoff[debts.at[idx, "id"]] = pd.Timestamp(date)  # Ensure it's explicitly a Timestamp
                newly_freed += debts.at[idx, "parcela"]

        snowball_extra += newly_freed

        records.append({
            "mes": m,
            "data_ref": date.date().isoformat(),
            "pago_minimo": round(min_pay_total, 2),
            "aporte_extra_usado": round(extra_used, 2),
            "snowball_para_prox": round(snowball_extra, 2),
            "juros_do_mes": round(interest_this_month, 2),
            "saldo_total": round(debts["saldo"].sum(), 2),
        })

        if debts["saldo"].sum() <= 0.01:
            break

    timeline = pd.DataFrame(records)
    payoff_df = pd.DataFrame([
        {"id": d["id"], "nome": d["nome"], "quitado_em": payoff[d["id"]].date().isoformat() if isinstance(payoff[d["id"]], pd.Timestamp) and not pd.isna(payoff[d["id"]]) else None}
        for _, d in debts_df.iterrows()
    ])
    return timeline, payoff_df, debts

if st.button("Rodar simulação"):
    debts_prepared = prepare_debts(dividas_edit, inpc_aa)
    timeline_df, payoff_df, final_debts = simulate(debts_prepared, st.session_state["aportes_edit"], horizonte_meses, BASE_START)

    st.success("Simulação concluída.")
    c1, c2 = st.columns([1,1])
    with c1:
        st.markdown("#### Cronograma (linha do tempo)")
        st.dataframe(timeline_df, use_container_width=True)
    with c2:
        st.markdown("#### Data de quitação por dívida")
        st.dataframe(payoff_df, use_container_width=True)

    st.markdown("#### Gráficos")
    fig1, ax1 = plt.subplots()
    ax1.plot(timeline_df["mes"], timeline_df["saldo_total"])
    ax1.set_xlabel("Mês")
    ax1.set_ylabel("Saldo total (R$)")
    ax1.set_title("Evolução do saldo total")
    st.pyplot(fig1)

    fig2, ax2 = plt.subplots()
    ax2.plot(timeline_df["mes"], timeline_df["pago_minimo"], label="Pago mínimo")
    ax2.plot(timeline_df["mes"], timeline_df["aporte_extra_usado"], label="Aporte extra usado")
    ax2.plot(timeline_df["mes"], timeline_df["snowball_para_prox"], label="Snowball p/ próximo mês")
    ax2.legend()
    ax2.set_xlabel("Mês")
    ax2.set_ylabel("R$")
    ax2.set_title("Fluxos mensais")
    st.pyplot(fig2)

    with pd.ExcelWriter("simulacao_dividas.xlsx", engine="xlsxwriter") as writer:
        timeline_df.to_excel(writer, index=False, sheet_name="timeline")
        payoff_df.to_excel(writer, index=False, sheet_name="quitacao")
        debts_prepared.to_excel(writer, index=False, sheet_name="dividas_usadas")
    st.markdown("[Baixar planilha da simulação (XLSX)](simulacao_dividas.xlsx)")

# ---------------- 4) Checklist do mês ----------------
st.markdown("### 4) Checklist do mês (pagamentos mínimos)")
competencia_default = compute_competencia(date.today(), BASE_DAY)
colc1, colc2 = st.columns([1,1])
with colc1:
    competencia = st.text_input("Competência (AAAA-MM)", value=competencia_default, help="Período de controle (base dia 20). Ex.: 2025-08")
with colc2:
    if st.button("Ir para competência atual"):
        competencia = compute_competencia(date.today(), BASE_DAY)

pagamentos_path = "pagamentos.csv"
if "pagamentos_df" not in st.session_state:
    pg_saved = load_csv_if_exists(pagamentos_path)
    if isinstance(pg_saved, pd.DataFrame):
        st.session_state["pagamentos_df"] = pg_saved
    else:
        st.session_state["pagamentos_df"] = pd.DataFrame(columns=["competencia","id","pago","data_pagamento"])

pag_df = st.session_state["pagamentos_df"].copy()

base = pd.DataFrame({"id": dividas_edit["id"], "nome": dividas_edit["nome"], "parcela": dividas_edit["parcela"]})
reg = pag_df[pag_df["competencia"] == competencia].copy()
status = base.merge(reg, how="left", on="id")
status["competencia"] = competencia
status["pago"] = status["pago"].fillna(False)
status["data_pagamento"] = status["data_pagamento"].fillna("")
status = status[["competencia","id","nome","parcela","pago","data_pagamento"]]

st.write("Marque as parcelas **pagas** nesta competência e salve:")
status_edit = st.data_editor(
    status,
    use_container_width=True,
    hide_index=True,
    column_config={
        "parcela": st.column_config.NumberColumn("Parcela (R$)", format="%.2f"),
        "pago": st.column_config.CheckboxColumn("Pago?"),
        "data_pagamento": st.column_config.TextColumn("Data do pagamento (AAAA-MM-DD)"),
    },
)

col_s1, col_s2, col_s3 = st.columns([1,1,1])
with col_s1:
    if st.button("Salvar checklist do mês"):
        other = pag_df[pag_df["competencia"] != competencia]
        tosave = status_edit[["competencia","id","pago","data_pagamento"]].copy()
        st.session_state["pagamentos_df"] = pd.concat([other, tosave], ignore_index=True)
        save_csv(st.session_state["pagamentos_df"], pagamentos_path)
        st.success(f"Checklist salvo para {competencia}.")
with col_s2:
    if st.button("Marcar todos como pagos"):
        status_edit["pago"] = True
        st.session_state["pagamentos_df"] = pd.concat([pag_df[pag_df["competencia"] != competencia], status_edit[["competencia","id","pago","data_pagamento"]]], ignore_index=True)
        save_csv(st.session_state["pagamentos_df"], pagamentos_path)
        st.success(f"Todas as parcelas marcadas como pagas para {competencia}.")
with col_s3:
    pend = status_edit[~status_edit["pago"]]["parcela"].sum()
    st.metric("Total pendente (mínimos) nesta competência", f"R$ {pend:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))

# ---------------- 5) Comparador de cenários ----------------
st.markdown("### 5) Comparador de cenários (aporte e INPC)")
colx1, colx2, colx3 = st.columns([1,1,1])
with colx1:
    meses_cmp = st.number_input("Horizonte de comparação (meses)", min_value=12, max_value=240, value=120, step=12)
with colx2:
    aporte_A = st.number_input("Aporte fixo cenário A (R$)", min_value=0.0, value=1500.0, step=100.0)
    inpc_A = st.number_input("INPC a.a. cenário A (%)", min_value=0.0, max_value=25.0, value=inpc_aa, step=0.1, key="inpc_A")
with colx3:
    aporte_B = st.number_input("Aporte fixo cenário B (R$)", min_value=0.0, value=2000.0, step=100.0)
    inpc_B = st.number_input("INPC a.a. cenário B (%)", min_value=0.0, max_value=25.0, value=inpc_aa, step=0.1, key="inpc_B")

def make_aportes_constantes(v, n):
    return pd.DataFrame({"mes": list(range(1, int(n)+1)), "aporte": [float(v)]*int(n)})

def prepare_debts_local():
    return st.session_state.get("dividas_edit", dividas_df).copy()

def run_and_summarize(dividas_local, aporte_const, inpc):
    debts = prepare_debts(dividas_local, inpc)
    ap = make_aportes_constantes(aporte_const, meses_cmp)
    timeline, payoff, _ = simulate(debts, ap, meses_cmp, BASE_START)
    meses_quit = int(timeline["mes"].iloc[-1])
    saldo_final = float(timeline["saldo_total"].iloc[-1])
    quitou = saldo_final <= 0.01
    return {
        "timeline": timeline,
        "payoff": payoff,
        "meses_quitacao": meses_quit,
        "saldo_final": saldo_final,
        "status": "QUITADO" if quitou else "NÃO QUITADO"
    }

if st.button("Comparar cenários"):
    div_local = prepare_debts_local()
    resA = run_and_summarize(div_local, aporte_A, inpc_A)
    resB = run_and_summarize(div_local, aporte_B, inpc_B)

    colr1, colr2 = st.columns([1,1])
    with colr1:
        st.subheader("Cenário A")
        st.write(f"Status: **{resA['status']}** — Meses simulados: **{resA['meses_quitacao']}** — Saldo final: **R$ {resA['saldo_final']:,.2f}**".replace(",", "X").replace(".", ",").replace("X","."))
        st.dataframe(resA["payoff"], use_container_width=True)
    with colr2:
        st.subheader("Cenário B")
        st.write(f"Status: **{resB['status']}** — Meses simulados: **{resB['meses_quitacao']}** — Saldo final: **R$ {resB['saldo_final']:,.2f}**".replace(",", "X").replace(".", ",").replace("X","."))
        st.dataframe(resB["payoff"], use_container_width=True)

    st.subheader("Evolução do saldo total — A vs B")
    figc, axc = plt.subplots()
    axc.plot(resA["timeline"]["mes"], resA["timeline"]["saldo_total"], label="Cenário A")
    axc.plot(resB["timeline"]["mes"], resB["timeline"]["saldo_total"], label="Cenário B")
    axc.set_xlabel("Mês")
    axc.set_ylabel("Saldo total (R$)")
    axc.set_title("Comparação de saldos")
    axc.legend()
    st.pyplot(figc)

    with pd.ExcelWriter("comparacao_cenarios.xlsx", engine="xlsxwriter") as writer:
        resA["timeline"].to_excel(writer, index=False, sheet_name="A_timeline")
        resA["payoff"].to_excel(writer, index=False, sheet_name="A_quitacao")
        resB["timeline"].to_excel(writer, index=False, sheet_name="B_timeline")
        resB["payoff"].to_excel(writer, index=False, sheet_name="B_quitacao")
    st.markdown("[Baixar planilha de comparação (XLSX)](comparacao_cenarios.xlsx)")

# ---------------- 6) Visão do mês (dashboard rápido) ----------------
st.markdown("### 6) Visão do mês (dashboard rápido)")
try:
    _div = st.session_state["dividas_edit"].copy()
    _apo = st.session_state["aportes_edit"].copy()
    competencia_dash = compute_competencia(date.today(), BASE_DAY)
    st.caption(f"Competência atual (base dia {BASE_DAY}): **{competencia_dash}**")
    total_minimos = float(_div.loc[_div["saldo_atual"] > 0, "parcela"].sum())
    aporte_mes = float(_apo.loc[_apo["mes"] == 1, "aporte"].sum()) if "mes" in _apo.columns else 0.0
    try:
        _pag = pd.read_csv("pagamentos.csv")
    except Exception:
        _pag = pd.DataFrame(columns=["competencia","id","pago","data_pagamento"])
    base_comp = _div[["id", "parcela"]].copy()
    pagos_comp = _pag[_pag["competencia"] == competencia_dash].copy().merge(base_comp, on="id", how="left")
    total_pago_mes = float(pagos_comp.loc[pagos_comp["pago"] == True, "parcela"].sum())
    pendente_mes = max(0.0, total_minimos - total_pago_mes)
    total_parcelas_original = float(_div["parcela"].sum())
    parcelas_ativas = float(_div.loc[_div["saldo_atual"] > 0, "parcela"].sum())
    liberado = max(0.0, total_parcelas_original - parcelas_ativas)
    perc_liberado = (liberado / total_parcelas_original) * 100.0 if total_parcelas_original > 0 else 0.0

    colv1, colv2, colv3, colv4, colv5 = st.columns(5)
    colv1.metric("Mínimos do mês", f"R$ {total_minimos:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
    colv2.metric("Aporte do mês", f"R$ {aporte_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
    colv3.metric("Pago (mínimos)", f"R$ {total_pago_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
    colv4.metric("Pendente (mínimos)", f"R$ {pendente_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
    colv5.metric("% orçamento liberado", f"{perc_liberado:.1f}%")

    figv, axv = plt.subplots()
    labels = ["Pago", "Pendente", "Aporte"]
    valores = [total_pago_mes, pendente_mes, aporte_mes]
    axv.bar(labels, valores)
    axv.set_ylabel("R$")
    axv.set_title("Resumo do mês")
    st.pyplot(figv)
except Exception as e:
    st.info("Edite suas dívidas e aportes acima para habilitar a 'Visão do mês'.")

# ---------------- 7) Tickar parcelas pagas agora (atalho) ----------------
st.markdown("### 7) Tickar parcelas pagas agora (atalho)")
try:
    comp_quick = compute_competencia(date.today(), BASE_DAY)
    st.caption(f"Competência sugerida: **{comp_quick}**")
    try:
        pag_quick = pd.read_csv("pagamentos.csv")
    except Exception:
        pag_quick = pd.DataFrame(columns=["competencia","id","pago","data_pagamento"])

    base_quick = pd.DataFrame({"id": dividas_edit["id"], "nome": dividas_edit["nome"], "parcela": dividas_edit["parcela"]})
    reg_quick = pag_quick[pag_quick["competencia"] == comp_quick].copy()
    status_quick = base_quick.merge(reg_quick, how="left", on="id")
    status_quick["competencia"] = comp_quick
    status_quick["pago"] = status_quick["pago"].fillna(False)
    status_quick["data_pagamento"] = status_quick["data_pagamento"].fillna("")
    status_quick = status_quick[["competencia","id","nome","parcela","pago","data_pagamento"]]

    quick_edit = st.data_editor(
        status_quick,
        use_container_width=True,
        hide_index=True,
        column_config={
            "parcela": st.column_config.NumberColumn("Parcela (R$)", format="%.2f"),
            "pago": st.column_config.CheckboxColumn("Pago?"),
            "data_pagamento": st.column_config.TextColumn("Data do pagamento (AAAA-MM-DD)"),
        },
    )

    qc1, qc2 = st.columns([1,1])
    with qc1:
        if st.button("Salvar agora (atalho)"):
            other = pag_quick[pag_quick["competencia"] != comp_quick]
            tosave = quick_edit[["competencia","id","pago","data_pagamento"]].copy()
            new_df = pd.concat([other, tosave], ignore_index=True)
            new_df.to_csv("pagamentos.csv", index=False)
            st.success(f"Pagamentos salvos para {comp_quick}.")
    with qc2:
        pend_q = quick_edit[~quick_edit["pago"]]["parcela"].sum()
        st.metric("Pendente após marcação", f"R$ {pend_q:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
except Exception as e:
    st.info("Preencha as dívidas acima para habilitar o atalho de marcação rápida.")
