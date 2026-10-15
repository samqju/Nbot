"""Read-only, private independent-review inboxes. Never signs approvals."""
import json
from pathlib import Path


def private_path(path, *, directory=False):
    path=Path(path)
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not (path.is_dir() if directory else path.is_file())
            or path.stat().st_mode & 0o077):
        raise ValueError("INDEPENDENT_REVIEW_PATH_UNSAFE")
    return path


def read_envelope(root, filename):
    path=Path(root)/filename
    if not path.exists():
        return None
    private_path(path)
    if path.stat().st_size>65536:
        raise ValueError("INDEPENDENT_REVIEW_FILE_BOUNDS")
    return json.loads(path.read_text())


class EconomicInbox:
    def __init__(self, root):
        self.root=private_path(root,directory=True)

    def __call__(self, population, intent, path, now_ms):
        item=read_envelope(self.root,intent["label_id"]+".json")
        if item is None:
            return None
        return item["evidence"],item["independent_review"]


class LearningReviewInbox:
    def __init__(self, root):
        self.root=private_path(root,directory=True)

    def __call__(self, subject, purpose, context, now_ms):
        if purpose not in ("G5_TRAINING","G6_PROMOTE"):
            raise ValueError("INDEPENDENT_REVIEW_PURPOSE")
        return read_envelope(self.root,purpose+"."+subject+".json")
