"""Assemble a portable package using an official Python embeddable ZIP and wheels.

Inputs must be downloaded from python.org and the official PyPI registry.
All files are built outside user data. No production database is included.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-zip", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, default=Path("wheelhouse"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    release = root / "release"
    release.mkdir(exist_ok=True)
    bundle = release / "GrupoAbogados_D_Honduras-Windows"
    if bundle.exists():
        raise SystemExit(
            "El paquete ya existe; use una carpeta de trabajo nueva o conserve el anterior."
        )
    bundle.mkdir()
    runtime = bundle / "runtime"
    runtime.mkdir()
    with zipfile.ZipFile(args.python_zip) as archive:
        archive.extractall(runtime)
    pth = next(runtime.glob("python*._pth"))
    pth.write_text(
        pth.read_text().replace("#import site", "import site") + "\nLib/site-packages\n..\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(args.wheels),
            "--target",
            str(runtime / "Lib" / "site-packages"),
            "-r",
            str(root / "requirements-lock.txt"),
        ],
        check=True,
    )
    for directory in ("backend", "scripts", "docs"):
        shutil.copytree(
            root / directory,
            bundle / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copytree(root / "frontend" / "dist", bundle / "frontend" / "dist")
    for name in ("Iniciar.cmd", "RecuperarSuperusuario.cmd", "README.md", "requirements-lock.txt"):
        shutil.copy2(root / name, bundle / name)
    (bundle / "CrearAccesoDirecto.ps1").write_text(
        "$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Grupo Abogados D Honduras.lnk'))\n$shortcut.TargetPath = Join-Path $PSScriptRoot 'Iniciar.cmd'\n$shortcut.WorkingDirectory = $PSScriptRoot\n$shortcut.Save()\n",
        encoding="utf-8",
    )
    manifest = {
        "version": "0.1.1",
        "python_zip_sha256": hashlib.sha256(args.python_zip.read_bytes()).hexdigest(),
        "files": {
            p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in bundle.rglob("*")
            if p.is_file()
        },
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = shutil.make_archive(
        str(release / "GrupoAbogados_D_Honduras-Windows-v0.1.1"), "zip", release, bundle.name
    )
    print(archive)


if __name__ == "__main__":
    main()
