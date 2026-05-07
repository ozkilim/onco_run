"""Optional helpers for predictor authors.

Nothing in `onco_run.helpers` is used by the runner itself. Import from
here only if it saves you work; you are free to ignore it entirely and
do your own slide IO.

Available helpers:
    onco_run.helpers.slide_io   -> OpenSlide wrapper (Slide context manager,
                                   thumbnail, mpp resolution)
    onco_run.helpers.tiling     -> tissue mask + tile coord generation
"""
