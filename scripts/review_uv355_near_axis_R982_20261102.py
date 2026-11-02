"""Independent R943 full-field audits for the source-refreshed squared-RMS branch."""
import time
import review_uv355_focal_design_R946_20261102 as original
original.UP=original.ROOT/'results/uv355_near_axis_design_R981_20261102'
original.OUT=original.ROOT/'results/uv355_near_axis_review_R982_20261102'
if __name__=='__main__':
    while not(original.UP/'progress.json').exists():
        assert not original.read(original.CHAT/'progress.json')['user_task_paused'];time.sleep(1)
    original.main()
