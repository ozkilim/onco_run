# onco_run — running predictions on your slides

You have received three things in this folder:

```
.
├── onco_run_image.tar.gz   # the docker image (model + everything inside)
├── run.sh                  # the only command you need
└── README.md               # this file
```

You need exactly **one** thing installed on the machine:

- **Docker** — Docker Desktop on macOS/Windows, or `docker-engine` on Linux.
  Verify with `docker --version`.

GPU is optional. If the machine has an NVIDIA GPU and the
`nvidia-container-toolkit` is installed, `run.sh` will use it
automatically. Otherwise it runs on CPU (slower but identical results).

---

## Steps

1. Put all your whole-slide image files into one folder. Subfolders are
   fine; nested files are scanned recursively. Common formats are
   supported: `.svs`, `.tif`, `.tiff`, `.ndpi`, `.mrxs`, `.scn`, etc.

2. Make a folder for the output. It can be empty.

3. Run:

   ```bash
   ./run.sh /path/to/slides_folder /path/to/output_folder
   ```

   The first run loads the image (a few minutes); subsequent runs skip
   that step.

4. When it finishes, send back:
   - `output_folder/predictions.csv` — one row per slide
   - `output_folder/run_summary.json` — counts and metadata
   - `output_folder/run.log` — log file (helps diagnose failures)

That's it.

---

## What's in `predictions.csv`

| Column            | Meaning                                                |
| ----------------- | ------------------------------------------------------ |
| `slide_id`        | Filename without extension                             |
| `slide_path`      | Path inside the container (`/data/slides/...`)         |
| `status`          | `ok` or `error`                                        |
| `predicted_class` | Argmax class                                           |
| `prob_<class>`    | Probability per class (one column per class)           |
| `elapsed_s`       | Per-slide wall time                                    |
| `error`           | Exception message if `status == "error"`               |

---

## Common questions

**Where does the data go?** Nowhere. Everything stays on your machine.

**My slide failed with `error`.** Send back `run.log`. Most often this
is a corrupt file or an unusually exotic vendor format.

**Can I run on a subset?** Yes — point `run.sh` at a folder containing
only the slides you want.

**It's slow on CPU.** Expected. Run on a GPU machine if you can.
