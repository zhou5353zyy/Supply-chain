# -*- coding: utf-8 -*-
"""
Inventory Optimization Analysis for Electrical Materials
=========================================================
A minimal end-to-end inventory analysis project for supply chain planning.

Pipeline: ABC classification -> Safety stock -> EOQ -> Replenishment kanban
Data    : sample_data.xlsx (12 categories of electrical materials, single sheet)

This mirrors classic Excel skills (VLOOKUP / SUMIFS / pivot) implemented in
plain Python/pandas to demonstrate data-analysis ability.

Run from the repository root:
    python src/inventory_optimization.py
"""
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths (relative to the repository root, so it runs from anywhere)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "sample_data.xlsx"
OUT_DIR = ROOT / "output"
FIG_DIR = ROOT / "figures"

# ---------------------------------------------------------------------------
# Model parameters
# ---------------------------------------------------------------------------
Z = 1.28             # service-level coefficient for 90% customer service level
LEAD_TIME = 0.5      # replenishment lead time in months (~2 weeks)
ORDER_COST = 200     # fixed cost per order (CNY)
HOLDING_RATE = 0.20  # annual holding cost as % of purchase cost

# ---------------------------------------------------------------------------
def main():
    df = pd.read_excel(DATA)
    print("Original table (first 5 rows):\n", df.head().to_string(), "\n")

    # ---- 1) ABC classification by annual consumption value -----------------
    dfc = df.copy()
    dfc["annual_value"] = dfc["采购成本"] * dfc["月销量"] * 12  # cost x annual demand
    dfc = dfc.sort_values("annual_value", ascending=False).reset_index(drop=True)
    dfc["cum_value"] = dfc["annual_value"].cumsum()
    total = dfc["annual_value"].sum()
    dfc["cum_pct"] = (dfc["cum_value"] / total).round(4)

    def abc(row):
        if row["cum_pct"] <= 0.70:
            return "A"   # top 70% of value -> tightly managed
        elif row["cum_pct"] <= 0.90:
            return "B"   # 70%-90% -> routine management
        return "C"       # remainder -> simplified management
    dfc["ABC_class"] = dfc.apply(abc, axis=1)

    print("=" * 68)
    print("1) ABC CLASSIFICATION (by annual consumption value)")
    print("=" * 68)
    print(dfc[["物料号", "物料名", "品类", "采购成本", "月销量",
               "annual_value", "cum_pct", "ABC_class"]].to_string(), "\n")

    # ---- 2) Safety stock ------------------------------------------------
    # Simplified lead-time demand model:
    #   SS = Z * (demand std per period) * sqrt(lead time)
    # Teaching approximation: treat monthly demand std as 30% of demand.
    dfc["safety_stock"] = (Z * dfc["月销量"] * 0.3 * (LEAD_TIME ** 0.5)).round(0)

    print("=" * 68)
    print("2) SAFETY STOCK (90% service level)")
    print("=" * 68)
    print(dfc[["物料号", "物料名", "月销量", "safety_stock"]].to_string(), "\n")

    # ---- 3) Economic Order Quantity (EOQ) -------------------------------
    # EOQ = sqrt( 2 * annual demand D * order cost S / holding cost H )
    dfc["EOQ"] = ((2 * dfc["月销量"] * 12 * ORDER_COST)
                  / (dfc["采购成本"] * HOLDING_RATE)) ** 0.5
    dfc["EOQ"] = dfc["EOQ"].round(0)

    print("=" * 68)
    print("3) ECONOMIC ORDER QUANTITY (EOQ)")
    print("=" * 68)
    print(dfc[["物料号", "物料名", "月销量", "采购成本", "EOQ"]].to_string(), "\n")

    # ---- 4) Replenishment kanban ----------------------------------------
    dfc["stock_turn"] = (dfc["库存量"] / dfc["月销量"]).round(2)

    def status(row):
        if row["库存量"] < row["safety_stock"]:
            return "URGENT restock"
        if row["stock_turn"] >= 2:
            return "OVERSTOCK risk"
        return "OK"
    dfc["status"] = dfc.apply(status, axis=1)

    print("=" * 68)
    print("4) REPLENISHMENT KANBAN (final result)")
    print("=" * 68)
    out = dfc[["物料号", "物料名", "ABC_class", "库存量",
               "safety_stock", "stock_turn", "EOQ", "status"]]
    print(out.to_string(), "\n")

    # ---- Export results -------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_excel(OUT_DIR / "inventory_optimization_result.xlsx", index=False)
    out.to_csv(OUT_DIR / "inventory_optimization_result.csv",
               index=False, encoding="utf-8-sig")
    print(f"Results written to {OUT_DIR}")

    # ---- Summary for the CV / talking points ---------------------------
    print()
    print("---- Project summary (resume points) ----")
    print("A-class items            :", int((dfc["ABC_class"] == "A").sum()))
    print("Items needing restock    :", int((dfc["status"] == "URGENT restock").sum()))
    print("Overstock items          :", int((dfc["status"] == "OVERSTOCK risk").sum()))

    # ---- 5) Visualization ----------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]  # Chinese fonts
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    # Left: ABC cumulative value share
    x = range(len(dfc))
    ax1.bar(x, dfc["annual_value"] / total, width=0.6,
            color="#8888aa", label="value share")
    ax1.plot(x, dfc["cum_pct"] * 100, color="#cc4444",
             marker="o", label="cumulative %")
    ax1.axhline(70, color="#44aa44", ls="--", lw=1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(dfc["物料名"], rotation=45, ha="right", fontsize=7)
    ax1.set_title("ABC classification: value concentrated in few items", fontsize=11)
    ax1.set_ylabel("value share / cumulative %")
    ax1.legend(fontsize=8)

    # Right: inventory level vs safety stock
    ax2.bar(x2 := range(len(dfc)), dfc["库存量"],
            color="#9bb8d4", label="current stock")
    ax2.bar(x2, dfc["safety_stock"], color="#e79b9b",
            alpha=0.7, label="safety stock")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(dfc["物料名"], rotation=45, ha="right", fontsize=7)
    ax2.set_yscale("log")
    ax2.legend(fontsize=8)
    ax2.set_title("Stock level vs safety stock", fontsize=11)

    plt.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIG_DIR / "inventory_visualization.png", dpi=150)
    plt.close()
    print(f"\nFigure saved: {FIG_DIR / 'inventory_visualization.png'}")


if __name__ == "__main__":
    main()