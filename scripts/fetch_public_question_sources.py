"""Download pinned public question releases; never access model credentials or MySQL."""

import hashlib
import json
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/question_bank_sources"
ASSETS = ROOT / "data/question_bank_assets"
RELEASES = {
    "gaokao": ("OpenLMLab/GAOKAO-Bench", "6dbb24f8d8439041e5431c4c184a582182a6ce9c"),
    "tal": ("math-eval/TAL-SCQ5K", "8a66d6e14c65ba002beda39747e6b7c43bd2d472"),
}


def fetch(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        partial = path.with_suffix(path.suffix + ".part")
        with (
            urllib.request.urlopen(url, timeout=180) as response,
            partial.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)
        partial.replace(path)
    with path.open("rb") as downloaded:
        digest = hashlib.file_digest(downloaded, "sha256").hexdigest()
    return {
        "url": url,
        "path": str(path.relative_to(ROOT)),
        "sha256": digest,
        "bytes": path.stat().st_size,
    }


def extract(archive, destination, strip_root=False):
    destination.mkdir(parents=True, exist_ok=True)

    def target(name):
        parts = Path(name).parts[1:] if strip_root else Path(name).parts
        path = destination.joinpath(*parts).resolve()
        if not path.is_relative_to(destination.resolve()):
            raise ValueError("Archive path outside destination")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                if not item.is_dir():
                    with z.open(item) as src, target(item.filename).open("wb") as dst:
                        shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive) as tar:
            for item in tar:
                if item.isfile():
                    with (
                        tar.extractfile(item) as src,
                        target(item.name).open("wb") as dst,
                    ):
                        shutil.copyfileobj(src, dst)


def main():
    manifest = []
    for key, (repo, revision) in RELEASES.items():
        archive = SOURCES / key / "release.zip"
        manifest.append(
            fetch(f"https://codeload.github.com/{repo}/zip/{revision}", archive)
        )
        extract(archive, SOURCES / key, True)
    manifest.append(
        fetch(
            "https://www.cs.cmu.edu/~glai1/data/race/RACE.tar.gz",
            SOURCES / "race/RACE.tar.gz",
        )
    )
    manifest.append(
        fetch(
            "https://www.cs.cmu.edu/~glai1/data/race/dist/index.js",
            SOURCES / "race/terms-page.js",
        )
    )
    for key, repo, revision, files in [
        (
            "cmm_math",
            "ecnu-icalk/cmm-math",
            "5b227e818a47ebfd0090b4fdcaac38cbf8cb7aa3",
            ["README.md", "all_data.jsonl", "images.zip"],
        ),
        (
            "cmmu",
            "BAAI/CMMU",
            "b3b65566fa083636713bca7b117e48c67720a074",
            ["README.md", "val/images.tar"]
            + [
                "val/" + s + ".jsonl"
                for s in [
                    "biology",
                    "chemistry",
                    "geography",
                    "history",
                    "math",
                    "physics",
                    "politics",
                ]
            ],
        ),
    ]:
        for name in files:
            path = SOURCES / key / Path(name).name
            manifest.append(
                fetch(
                    f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{name}",
                    path,
                )
            )
            if path.suffix in {".zip", ".tar"}:
                extract(path, ASSETS / key)
    (SOURCES / "expansion-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {
                "downloaded_files": len(manifest),
                "manifest": str(SOURCES / "expansion-manifest.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
