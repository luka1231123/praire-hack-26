// Placeholder numbers copied from README.md. Run `uv run export_site.py` to replace this file with the full export.
window.DATA = {
  "seed": true,
  "platform": "telegram",
  "min_posts": 20,
  "overview": {"posts": 17300000, "users": null, "start": null, "end": null, "threads": 13,
               "labeled_users": 15856, "active_users": null, "active_labeled": null, "base_rate": 0.031},
  "monthly": null,
  "channels": null,
  "schedule": null,
  "lift": {"random_pair": 0.007, "signals": [
    {"signal": "dup", "name": "Same template text", "lift": 94},
    {"signal": "item", "name": "Same link or hashtag", "lift": 9},
    {"signal": "tgt", "name": "Same reply targets", "lift": 5}]},
  "precision": [{"k": 10, "users": 655, "labeled": 0.464},
                {"k": 50, "users": 1231, "labeled": 0.526},
                {"k": 200, "users": 2540, "labeled": 0.413}],
  "n_groups": null,
  "groups": null,
  "scatter": null,
  "networks": null
};
