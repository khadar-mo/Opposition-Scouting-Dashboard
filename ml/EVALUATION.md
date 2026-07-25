# xT model — methodology and evaluation

## What the model is

A possession-value model $V(x, y)$: from a ball position, the probability-weighted
shot value (xG) the possession will produce **within the next 5 on-ball actions**.
Every completed pass and carry is then credited with the change in threat it
produced, $\Delta V = V(\text{end}) - V(\text{start})$.

- **Architecture**: MLP `4 → 64 → 64 → 1` (PyTorch), sigmoid output.
  Inputs: normalised $(x, y)$ plus distance and angle to goal, redundant
  encodings that let a small network learn the goal-centric geometry quickly.
- **Labels**: soft labels in $[0, 1]$, the summed StatsBomb xG of shots taken by
  the possessing team within the next 5 actions, capped at 1. Training loss is
  binary cross-entropy on these soft labels.
- **Data**: all 422,561 events / ~330k on-ball actions across the ingested
  tournaments. 2022 FIFA World Cup (64 matches) + UEFA Euro 2024 (51 matches),
  StatsBomb open data. One model serves both competitions; per-team threat
  aggregates are computed per tournament.
- **Split**: **by match** (80/20). Actions from the same match never appear on
  both sides, so validation measures generalisation to unseen games.
- **Aggregation**: the dashboard sums **positive** ΔV ("threat created").
  Negative ΔV is possession recycling, safe back-passes and including it
  would hide progressive players behind their tidy circulation.

## Results

| Check | Result |
|---|---|
| Validation BCE vs base-rate baseline | **0.0227 vs 0.0303** (25.0% better) |
| Threat monotonic towards goal (along y=40) | **100%** of steps increasing |
| Central vs wide value at x=108 | **0.160 vs 0.010** — central dominates |
| Own box / halfway / penalty spot | 0.00002 / 0.002 / 0.160 |
| Spearman rank corr. with Karun Singh's public xT grid | **0.985** |
| Calibration (validation deciles) | observed tracks predicted (see notebook) |

The Karun Singh comparison matters most: his grid was derived from *different
data* (2017-18 Premier League) with a *different method* (value iteration on a
12×8 grid). A rank correlation of 0.985 means this model recovers the same
geography of threat independently.

**Eye test**: the top creators by positive ΔV per 90 (min. 270 minutes,
per tournament) are Dembélé, Di María, Musiala, Raphinha, De Bruyne and from
Euro 2024, Lamine Yamal, Doku and Nico Williams. No player information was
ever given to the model, it sees only ball positions.

## Does defensive context matter? A 360 ablation

The 360 freeze-frames let us test whether the *defensive picture* at the moment
of an action carries signal beyond ball position. For every covered on-ball
action (88% of them - 198,354 actions) we compute three features from opponent
positions: nearest-defender distance, defenders goal-side of the ball, and
defenders inside the ball→goalposts cone. Then two identical MLPs, identical
match-level split, identical budget, on the identical subset:

| Model | Validation BCE |
|---|---|
| Base rate | 0.0317 |
| Position only (x, y) | 0.02375 |
| Position + defender context | **0.02301** (3.1% better) |

**Interpretation**: position dominates - where the ball is explains most of the
threat, but defensive context adds a small, real improvement. That is exactly
what football intuition predicts: the same zone is worth less against a set
block than in transition.

**A free validation of StatsBomb's `under_pressure` flag**: the median
360-measured nearest-defender distance is **2.5 pitch units when the flag is
set vs 6.5 when it is not**. Two independent data channels agree.

**Product decision**: the deployed scorer stays position-only. Crediting an
action needs V at its *end* location, where no freeze-frame exists (the frame
belongs to the action's start), so a context model would silently degrade to
position-only for half of every ΔV anyway. Instead, the dashboard uses the
(now independently validated) `under_pressure` flag, full coverage, zero
inference, to split each team's threat map into all origins vs
pressure-resistant origins. Run the ablation: `python -m ml.pressure_ablation`.

## Honest limitations

- **Sample size**: a tournament gives each team 3–7 matches; per-team maps are
  tendencies, not certainties. The UI shows action counts wherever threat is
  aggregated, and never mixes tournaments in one aggregate.
- **Position-only value**: no pressure, game state, or player-quality context.
  A 2-0-up counter and a desperate 89th-minute possession look the same.
- **Set-piece inheritance**: corner/free-kick actions inherit open-play values;
  the set-piece view therefore uses delivery/first-contact data, not xT.
- **k=5 horizon**: chosen so credit stays local to the sequence of play;
  results are not sensitive to k∈{4,6} (spot-checked).

## Reproducing

```bash
uv run python -m ml.train        # trains, writes ml/artifacts/xt_model.pt + metrics
uv run python -m ml.xt_apply     # writes zone_threat / player_threat tables
uv run python -m ml.cluster      # build-up pattern clustering (k-means, k=8)
uv run python ml/notebooks/build_notebook.py   # regenerate evaluation notebook
uv run jupyter nbconvert --to notebook --execute --inplace ml/notebooks/xt_evaluation.ipynb
```

## Build-up pattern clustering

Sequences that reach the final third (≥4 on-ball actions, open-play patterns)
are clustered with k-means (k=8) on standardised features: start position,
progression, directness, tempo, width variability, duration, action count, and
a one-hot of the **lane of final-third entry** (weighted ×2, where a team
enters the final third is the pattern's identity for an analyst). One global
model keeps labels comparable across teams; per-team usage shares and
representative sequences are stored for the dashboard. k=8 was chosen as the
best trade-off between silhouette score (0.17→0.24 over k=6..10, no elbow) and
a set of clusters a coach can actually name.
