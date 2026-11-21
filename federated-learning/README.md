# Federated hospital units

Privacy-preserving federated learning for the sepsis early-warning system. Every hospital has
its own unit that keeps its patient data, trains locally and runs predictions with models
personalised on its own patients. Hospitals improve a shared model through a central server:

    hospital units --signed updates--> Security Layer -> Orchestrator Agent
                                       -> Federated Aggregation (FedAvg / FedProx) -> Global Model
    Global Model --universal update--> every hospital unit, next round

The design is described in `docs/E6_Federated_Unit_Report.pdf`.

## Layout

| File | Role |
|---|---|
| `fedsepsis/config.py` | The 39 PhysioNet variables, window, split and threshold settings |
| `fedsepsis/data.py` | Loading a hospital's `.psv` files, cleaning, patient split, 16-hour windows, ICU-type clients |
| `fedsepsis/fedstats.py` | Federated median imputer and scaler from histograms and sums |
| `fedsepsis/models.py` | Logistic Regression, LSTM, GRU and Temporal CNN in PyTorch |
| `fedsepsis/unit.py` | `HospitalUnit`: local training, tree models, personalisation |
| `fedsepsis/security.py` | Security Layer: HMAC-SHA256 signing and verification |
| `fedsepsis/orchestrator.py` | Orchestrator Agent: validates and filters updates |
| `fedsepsis/server.py` | Central server rounds, aggregation, attack simulation |
| `fedsepsis/experiment.py` | Local, FedAvg, FedProx and centralised schemes; artifacts; results JSON |
| `fedsepsis/inference.py` | `HospitalPredictor`: scores one window with audit fields |
| `run_federated.py` | Command line |
| `tests/` | Synthetic test data generator and tests |

## Run

Put the PhysioNet 2019 folders `training_setA` and `training_setB` under `data/`, then:

    pip install -r requirements.txt
    python run_federated.py \
      --hospital A "Hospital A (PhysioNet set A)" data/training_setA \
      --hospital B "Hospital B (PhysioNet set B)" data/training_setB \
      --rounds 5 --artifacts artifacts --out results/federated_results.json

Options:

- `--split-by-icu` turns each hospital into one client per ICU type (non-IID clients).
- `--attack B scale` makes client B send a faulty update (`scale`, `signflip`, `noise`, `nan`,
  `tamper`) to show the Security Layer and Orchestrator Agent rejecting it.
- `--schemes fedavg fedprox` runs only the federated schemes; `--neural gru lstm` and
  `--trees lightgbm` choose models; `--limit 2000` uses the first 2,000 patients per
  hospital for a quick trial.

A GPU is used automatically when PyTorch finds one.

## Tests

    python tests/make_synthetic.py           # optional: writes synthetic hospitals
    python -m pytest -q tests

The synthetic files contain random values with a built-in signal. They only check that the
code works; results on them say nothing about sepsis.
