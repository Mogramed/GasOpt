"""Reproducible presentation figures with explicit TRAIN/TEST and data labels."""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gasopt.config import ExperimentConfig


def save_study_plots(
    slots: pd.DataFrame, workload_observations: pd.DataFrame, study: dict,
    config: ExperimentConfig, output: Path, *, label: str,
) -> list[Path]:
    """Save PNG/PDF figures. Callers must explicitly label empirical vs fixture data."""
    output.mkdir(parents=True, exist_ok=True)
    files = []

    def save(fig, name: str) -> None:
        fig.text(.01, .01, label + " | UTC slots | ETH costs", fontsize=8, color="#536477")
        fig.tight_layout(rect=(0, .04, 1, 1))
        for extension in ("png", "pdf"):
            target = output / f"{name}.{extension}"
            fig.savefig(target, dpi=220, bbox_inches="tight")
            files.append(target)
        plt.close(fig)

    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "axes.labelcolor": "#20344b"}):
        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.plot(slots.slot_start_utc, slots.median_gas_price_gwei, color="#226e8b", lw=.8)
        ax.axvspan(pd.Timestamp(config.test_start, tz="UTC"),
                   pd.Timestamp(config.test_end, tz="UTC") + pd.Timedelta(days=1),
                   color="#e8ac65", alpha=.2, label="TEST (evaluation only)")
        ax.set(title="Ethereum two-hour slot medians through time", ylabel="Gas price (gwei/gas)", xlabel="UTC date")
        ax.legend(frameon=False)
        save(fig, "01_gas_price_through_time")

        fig, ax = plt.subplots(figsize=(10, 4.5))
        for data, split, color in ((study["train_slots"], "TRAIN", "#226e8b"),
                                    (study["test_slots"], "TEST (descriptive)", "#b46a27")):
            medians = data.groupby("slot").median_gas_price_gwei.median()
            ax.plot(medians.index, medians, marker="o", label=split, color=color)
        ax.set(title="Median across days of each slot's median price", xlabel="Two-hour UTC slot",
               ylabel="Gas price (gwei/gas)", xticks=range(1, 13))
        ax.legend(frameon=False)
        save(fig, "02_price_by_slot")

        wide = slots.pivot(index="day", columns="slot", values="median_gas_price_gwei")
        fig, ax = plt.subplots(figsize=(10, 6))
        mesh = ax.imshow(wide.to_numpy(), aspect="auto", interpolation="nearest", cmap="cividis")
        tick_rows = np.unique(np.linspace(0, len(wide) - 1, min(8, len(wide))).astype(int))
        ax.set(xticks=range(12), xticklabels=range(1, 13), yticks=tick_rows,
               yticklabels=[pd.Timestamp(wide.index[i]).strftime("%Y-%m-%d") for i in tick_rows],
               xlabel="Two-hour UTC slot", ylabel="Retained UTC day", title="Whole-day price trajectories")
        boundary = np.searchsorted(wide.index, pd.Timestamp(config.test_start, tz="UTC"))
        ax.axhline(boundary - .5, color="white", lw=1.5)
        fig.colorbar(mesh, ax=ax, label="Median gas price (gwei/gas)")
        save(fig, "03_day_slot_heatmap")

        schedules = study["fitted"].schedules
        selected_cvar = f"cvar_lambda_{max(config.lambda_grid):g}"
        strategies = ("immediate", "mean_price", selected_cvar)
        fig, ax = plt.subplots(figsize=(11, 8))
        for i, tx in enumerate(study["transactions"]):
            ax.plot([tx.release_slot, tx.deadline], [i, i], color="#d5dce1", lw=4, solid_capstyle="round")
        for name, color, marker, offset in zip(strategies, ("#68747e", "#226e8b", "#b46a27"), ("o", "s", "D"), (-.15, 0, .15)):
            ax.scatter([schedules[name][tx.id] for tx in study["transactions"]],
                       np.arange(len(study["transactions"])) + offset, color=color, marker=marker,
                       s=22, label=name, zorder=3)
        ax.set(yticks=range(len(study["transactions"])), yticklabels=[tx.id for tx in study["transactions"]],
               xticks=range(1, 13), xlabel="Assigned UTC slot (grey line: feasible window)",
               title="Frozen schedules; displayed CVaR weight is the grid maximum")
        ax.invert_yaxis()
        ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1, 1))
        save(fig, "04_schedule_comparison")

        fig, ax = plt.subplots(figsize=(10, 5))
        costs = study["test_daily_costs"]
        ax.boxplot([costs[name] for name in strategies], tick_labels=strategies, showmeans=True,
                   medianprops={"color": "#b46a27", "linewidth": 2})
        ax.set(title="TEST costs of frozen schedules", ylabel="Daily workload cost (ETH)")
        save(fig, "05_test_cost_distributions")

        train_metrics = study["fitted"].training_metrics
        curve = train_metrics[train_metrics.strategy.str.startswith("cvar_")].sort_values("lambda_risk")
        test_metrics = study["test_metrics"].set_index("strategy")
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for ax, split in zip(axes, ("TRAIN", "TEST")):
            x = curve.train_expected_cost_eth if split == "TRAIN" else test_metrics.loc[curve.strategy, "test_mean_cost_eth"]
            y = curve.train_cvar_eth if split == "TRAIN" else test_metrics.loc[curve.strategy, "test_cvar_eth"]
            points = ax.scatter(x, y, c=curve.lambda_risk, cmap="viridis", s=55)
            ax.plot(np.asarray(x), np.asarray(y), color="#95a2ac", alpha=.5)
            ax.set(title=f"{split}: cost vs CVaR", xlabel="Expected cost (ETH)" if split == "TRAIN" else "Mean cost (ETH)",
                   ylabel=f"CVaR at alpha={config.alpha:g} (ETH)")
            fig.colorbar(points, ax=ax, label="Risk weight lambda")
        save(fig, "06_cost_risk_tradeoff")

        fig, axes = plt.subplots(2, 1, figsize=(11, 9), gridspec_kw={"height_ratios": [1, 2]})
        axes[0].plot(curve.lambda_risk, curve.train_expected_cost_eth, marker="o", label="TRAIN expected cost")
        axes[0].plot(curve.lambda_risk, curve.train_cvar_eth, marker="s", label="TRAIN CVaR")
        axes[0].set(xlabel="Risk weight lambda", ylabel="ETH", title="Training sensitivity to risk aversion")
        axes[0].legend(frameon=False)
        matrix = np.array([[schedules[name][tx.id] for name in curve.strategy] for tx in study["transactions"]])
        image = axes[1].imshow(matrix, aspect="auto", cmap="viridis", vmin=1, vmax=12, interpolation="nearest")
        axes[1].set(xticks=range(len(curve)), xticklabels=[f"{x:g}" for x in curve.lambda_risk],
                    yticks=range(len(study["transactions"])), yticklabels=[tx.id for tx in study["transactions"]],
                    xlabel="Risk weight lambda", title="Assigned slot for every fixed transaction")
        axes[1].tick_params(axis="y", labelsize=7)
        fig.colorbar(image, ax=axes[1], label="Assigned UTC slot", ticks=[1, 3, 6, 9, 12])
        save(fig, "07_lambda_sensitivity")

        table = study["test_metrics"]
        fig, ax = plt.subplots(figsize=(12, max(4, .36 * len(table) + 1.5)))
        ax.axis("off")
        text = [[r.strategy, f"{r.test_mean_cost_eth:.7f}", f"{r.test_cvar_eth:.7f}",
                 f"{r.test_max_cost_eth:.7f}", f"{r.test_savings_percent:.2f}%"] for r in table.itertuples(index=False)]
        artist = ax.table(cellText=text, colLabels=["Strategy", "Mean ETH", "CVaR ETH", "Worst ETH", "Mean savings"],
                          loc="center", cellLoc="right", colWidths=[.28, .18, .18, .18, .18])
        artist.auto_set_font_size(False)
        artist.set_fontsize(9)
        artist.scale(1, 1.55)
        for (row, column), cell in artist.get_celld().items():
            cell.set_edgecolor("#d5dce1")
            if row == 0:
                cell.set_facecolor("#20344b")
                cell.set_text_props(color="white", weight="bold")
            elif row % 2 == 0:
                cell.set_facecolor("#f1f5f7")
        ax.set_title("TEST strategy comparison — no lambda selected on TEST", pad=20)
        save(fig, "08_strategy_comparison")

        fig, ax = plt.subplots(figsize=(9, 4.5))
        prices = study["train_slots"].median_gas_price_gwei
        ax.hist(prices, bins=40, color="#226e8b", edgecolor="white")
        ax.set(title="TRAIN distribution of two-hour median prices", xlabel="Gas price (gwei/gas)", ylabel="Slot count")
        save(fig, "09_training_price_distribution")

        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.hist(workload_observations.gas_used, bins=45, color="#226e8b", alpha=.8, label="TRAIN sample")
        for value in study["workload"].gas_used:
            ax.axvline(value, color="#b46a27", alpha=.25, lw=.8)
        ax.set(title="TRAIN observed gas usage; lines mark selected workload values", xlabel="Gas consumed (gas)", ylabel="Observation count")
        save(fig, "10_training_gas_used_distribution")
    return files
