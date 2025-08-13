import os
import subprocess
import requests
import csv
import json
from packaging import version  # For version comparison
from flask import Flask, render_template, request, redirect, url_for, send_file

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ILLEGAL_LIBRARIES = {"malware-lib", "banned-lib"}  # Example illegal libraries

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("index"))

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    return redirect(url_for("analyze_dependencies", filename=file.filename))

def check_library_versions(dependencies):
    """Check if installed libraries are up to date."""
    outdated_libs = []
    for dep in dependencies:
        parts = dep.strip().split("==")
        if len(parts) != 2:
            continue  # Skip incorrectly formatted lines

        lib_name, installed_version = parts  # Extract library name & installed version
        try:
            # Fetch latest version from PyPI
            response = requests.get(f"https://pypi.org/pypi/{lib_name}/json", timeout=5)
            if response.status_code == 200:
                latest_version = response.json()["info"]["version"]

                # Compare versions using proper version parsing
                if version.parse(installed_version) < version.parse(latest_version):
                    outdated_libs.append(f"{lib_name}: Installed ({installed_version}), Latest ({latest_version})")
            else:
                outdated_libs.append(f"{lib_name}: Could not fetch latest version.")
        except Exception as e:
            outdated_libs.append(f"{lib_name}: Unable to check version ({str(e)})")

    return outdated_libs

@app.route("/analyze/<filename>")
def analyze_dependencies(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    dependencies = []
    illegal_libs = []
    outdated_libs = []

    if os.path.exists(filepath):
        with open(filepath, "r") as file:
            dependencies = [line.strip() for line in file if line.strip()]

        # Check for illegal libraries
        for dep in dependencies:
            lib_name = dep.split("==")[0]
            if lib_name in ILLEGAL_LIBRARIES:
                illegal_libs.append(lib_name)

        # Check outdated libraries
        outdated_libs = check_library_versions(dependencies)

        # Save report as CSV
        csv_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename}.csv")
        with open(csv_filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Dependency", "Category"])
            for dep in dependencies:
                writer.writerow([dep, "Uploaded"])
            for outdated in outdated_libs:
                writer.writerow([outdated, "Outdated"])
            for illegal in illegal_libs:
                writer.writerow([illegal, "Illegal"])

        # Save report as JSON
        json_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename}.json")
        report_data = {
            "filename": filename,
            "dependencies": dependencies,
            "outdated_libs": outdated_libs,
            "illegal_libs": illegal_libs
        }
        with open(json_filepath, "w") as jsonfile:
            json.dump(report_data, jsonfile, indent=4)

    return render_template(
        "report.html",
        filename=filename,
        dependencies=dependencies,
        outdated_libs=outdated_libs,
        illegal_libs=illegal_libs
    )

@app.route("/download/csv/<filename>")
def download_csv(filename):
    csv_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename}.csv")
    return send_file(csv_filepath, as_attachment=True)

@app.route("/download/json/<filename>")
def download_json(filename):
    json_filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{filename}.json")
    return send_file(json_filepath, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
