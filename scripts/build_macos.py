"""Build a source launcher anywhere, or a self-contained application on macOS."""
import argparse
import os
from pathlib import Path
import plistlib
import platform
import shutil
import subprocess
import sys
import zipfile
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]


def icon(directory):
    directory.mkdir(parents=True,exist_ok=True)
    image=Image.new("RGBA",(1024,1024),(0,0,0,0))
    drawing=ImageDraw.Draw(image)
    drawing.rounded_rectangle((40,40,984,984),radius=220,fill="#203b32")
    drawing.polygon([(520,150),(710,430),(735,610),(660,785),(510,850),(350,790),(278,650),(300,490),(395,350),(402,520),(482,410)],fill="#ee9a58")
    drawing.polygon([(520,480),(610,630),(604,720),(525,779),(440,726),(428,650)],fill="#f9ddb0")
    image.save(directory/"Ember.icns",format="ICNS")


def archive_app(app, destination, note):
    # ditto retains the app bundle's metadata on an actual Mac.
    if sys.platform=="darwin":
        subprocess.run(["ditto","-c","-k","--sequesterRsrc","--keepParent",str(app),str(destination)],check=True)
    else:
        with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(app.rglob("*")):
                if file.is_file():
                    archive.write(file,str(Path(app.name)/file.relative_to(app)))
    with zipfile.ZipFile(destination,"a",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("START-HERE.txt",note)


def launcher(output):
    app=output/"Ember.app"
    if app.exists():
        shutil.rmtree(app)
    contents=app/"Contents"
    (contents/"MacOS").mkdir(parents=True)
    (contents/"Resources/source").mkdir(parents=True)
    source=contents/"Resources/source"
    for name in ["ember","scripts","packaging"]:
        shutil.copytree(ROOT/name,source/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    for name in ["requirements.lock","requirements-desktop.lock","pyproject.toml","README.md","THIRD_PARTY_NOTICES.md"]:
        shutil.copyfile(ROOT/name,source/name)
    icon(contents/"Resources")
    plist={"CFBundleExecutable":"Ember","CFBundleName":"Ember","CFBundleDisplayName":"Ember",
        "CFBundleIdentifier":"me.lemien.ember.launcher","CFBundlePackageType":"APPL",
        "CFBundleShortVersionString":"2.2.0","CFBundleVersion":"220","CFBundleIconFile":"Ember.icns",
        "NSHighResolutionCapable":True,"LSMinimumSystemVersion":"10.15"}
    (contents/"Info.plist").write_bytes(plistlib.dumps(plist))
    executable=contents/"MacOS/Ember"
    executable.write_text('#!/bin/bash\nset -euo pipefail\nCONTENTS="$(cd "$(dirname "$0")/.." && pwd)"\nif [[ "${1:-}" == -psn_* ]]; then shift; fi\nexec /bin/bash "$CONTENTS/Resources/source/scripts/mac_bootstrap.sh" "$@"\n')
    executable.chmod(0o755)
    return app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-only",action="store_true",help="Needs an installed Python 3.12+ and internet for first-run dependencies")
    parser.add_argument("--output",type=Path,default=ROOT/"dist")
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if args.launcher_only:
        app=launcher(output)
        result=output/"Ember-Mac-launcher.zip"
        archive_app(app,result,"Ember 2.2 — Mac source launcher\n\nUnzip, then open Ember.app. First launch needs Python 3.12+ and internet to prepare its dependencies. If Python is missing, Ember offers the official download page. Reopen Ember after installing Python.\n\nChoose your owner password in the first-run window. Data stays in ~/Library/Application Support/Ember. Scanning runs while Ember is open and monitoring is enabled. eBay scanning needs eligible production API credentials; Cardmarket listings are manual/imported.\n\nThis launcher was assembled on Linux. Finder launch, Cocoa/WebKit and native notifications have not been verified on macOS. It is not a tested standalone Mac binary. The source ZIP includes Build-Mac-App.command for a self-contained build on your Mac, the VS Code workspace, Git history and complete instructions.\n")
        print(f"Created source launcher: {result}. macOS execution has not been verified by this build.")
        return
    if sys.platform!="darwin":
        parser.error("A standalone Mac executable must be built on macOS. Use --launcher-only here, or run Build-Mac-App.command on your Mac.")
    icon(ROOT/"build")
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--distpath",str(output),str(ROOT/"packaging/Ember.spec")],cwd=ROOT,check=True)
    app=output/"Ember.app"
    # Ad-hoc signing is not Developer ID signing or Apple notarization.
    subprocess.run(["codesign","--force","--deep","--sign","-",str(app)],check=True)
    result=output/("Ember-macOS-"+platform.machine()+".zip")
    archive_app(app,result,"Ember 2.2 — standalone Mac application\n\nOpen Ember.app, then choose your owner password. Your data is stored in ~/Library/Application Support/Ember.\n\nBuilt for "+platform.machine()+". Ad-hoc signed; not Apple-notarized. Verify the native interface and desktop notifications on the target Mac. Scans run while the app is open.\n")
    print(f"Created {result}; ad-hoc signed, not Apple-notarized. Verify it on the target Mac.")


if __name__=="__main__":
    main()
