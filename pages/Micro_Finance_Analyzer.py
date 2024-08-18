"""
Analyze Micro Finance in portfolio

author: 2024-08 Marek Ozana
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import streamlit as st
from scipy.stats import norm

import src.charts as charts
import src.optimization as opt

st.set_page_config(
    page_title="SEB Micro Finance Analyser",
    layout="wide",
    page_icon="💸",
)

logger: logging.Logger = logging.getLogger(__name__)


def load_data() -> None:
    if "corr" in st.session_state:
        logger.debug("ignoring load_data because data already exist")
        return

    logger.info("Reading in data and calculating params")
    rets = pd.read_csv("data/micfin_q_rets.csv", index_col=0, parse_dates=True)
    st.session_state["orig_rets"] = rets

    exp_rets = pd.read_csv("data/micfin_exp_rets.csv", index_col=0).squeeze()
    st.session_state["orig_exp_rets"] = exp_rets

    vols = rets.std() * 2  # * sqrt(4) for quarterly
    vols.name = "Vol"
    st.session_state["orig_vols"] = vols

    corr = rets.corr()
    st.session_state["orig_corr"] = corr.round(2)


def get_user_input() -> None:
    with st.sidebar:
        st.title("Parameters")
        r_min = (
            st.slider(
                "Min Required Return",
                min_value=0.1,
                max_value=10.0,
                step=0.1,
                value=7.0,
                format="%.1f%%",
                help="Constraint on minimum required return",
            )
            / 100
        )
        st.session_state["r_min"] = r_min

        all_tickers = st.session_state["orig_corr"].columns.tolist()
        tickers = st.multiselect(
            label="Tickers",
            options=all_tickers,
            default=all_tickers[:-1],
            help="Select Tickers for the optimization",
        )
        st.session_state["tickers"] = tickers

        with st.popover("Exp Returns"):
            exp_rets = st.data_editor(
                st.session_state["orig_exp_rets"] * 100,
                use_container_width=True,
                column_config={
                    "exp_ret": st.column_config.NumberColumn(
                        "Exp Return [%]", format="%0.1f %%"
                    ),
                },
            )
            st.session_state["exp_rets"] = exp_rets.div(100)

        with st.popover("Volatilities"):
            vols = st.data_editor(
                st.session_state["orig_vols"] * 100,
                use_container_width=False,
                column_config={
                    "Vol": st.column_config.NumberColumn(
                        "Volatility [%]", format="%0.1f %%"
                    ),
                },
            )
            st.session_state["vols"] = vols.div(100)

        with st.popover("Correlations"):
            corr = st.data_editor(
                st.session_state["orig_corr"] * 100,
                use_container_width=True,
                column_config={
                    col: st.column_config.NumberColumn(
                        format="%.0f%%", min_value=-100, max_value=100
                    )
                    for col in st.session_state["orig_corr"].columns
                },
            )
            st.session_state["corr"] = corr.div(100)


def main() -> None:
    st.title("Micro Finance Analyzer")
    load_data()  # Just once

    get_user_input()

    # get covar and calculate optimal portfolio
    tickers = st.session_state["tickers"]
    vols = st.session_state["vols"].loc[tickers]
    corr = st.session_state["corr"].loc[tickers, tickers]
    vol_d = np.diag(vols.values)
    cov = vol_d @ corr.values @ vol_d
    exp_rets = st.session_state["exp_rets"].loc[tickers]
    r_min = st.session_state["r_min"]
    w, r_opt, vol_opt = opt.find_min_var_portfolio(exp_rets, cov, r_min)
    
    # Create Scatter chart and Portfolio Composition Chart
    g_data = pl.DataFrame(
        {
            "name": tickers + ["OPTIMAL"],
            "vols": vols.to_list() + [vol_opt],
            "rets": exp_rets.to_list() + [r_opt],
            "w_opt": w.tolist() + [1],
        }
    )
    f_sc = charts.create_scatter_chart(g_data, None)
    f_w = charts.create_portf_weights_chart(g_data)
    title = f"Optimal Portfolio: r={r_opt:0.1%}, vol={vol_opt:0.1%}"
    col1, col2 = st.columns([1.5, 1])
    col1.altair_chart(f_sc, use_container_width=True)
    col2.altair_chart(f_w.properties(title=title, height=350), use_container_width=True)
    st.markdown(
        f"""
        ### Optimal Portfolio Statistics
        * **Expected Return in 1y** = {r_opt:0.1%}
        * **Expected volatility** = {vol_opt:0.1%}
        * 95%-prob Lowest Expected Return in 1y = {(r_opt - norm.ppf(0.95)*vol_opt):0.1%}
        * 99%-prob Lowest Expected Return in 1y = {(r_opt - norm.ppf(0.99)*vol_opt):0.1%}
        """
    )

    st.divider()
    st.caption(Path("data/disclaimer.txt").read_text())


# Entry point for the script
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)
    main()