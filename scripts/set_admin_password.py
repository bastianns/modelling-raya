#!/usr/bin/env python3
"""
Bank Raya - Secure Admin Password Setter for Azimutt
Security Standard: Zero-Credential-Exposure Architecture
"""

import os
import sys
import re
import getpass
import shutil
import subprocess
from pathlib import Path

def find_docker_bin() -> str:
    """Find docker executable across system paths."""
    docker_in_path = shutil.which("docker")
    if docker_in_path:
        return docker_in_path
    common_paths = [
        Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"),
        Path(r"C:\Program Files\Docker\Docker\resources\docker.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "resources" / "bin" / "docker.exe"
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return "docker"

def main():
    try:
        import bcrypt
    except ImportError:
        print("[ERROR] Modul 'bcrypt' belum terpasang.")
        print("Silakan pasang dependensi dengan menjalankan: pip install bcrypt")
        sys.exit(1)

    print("=" * 60)
    print("BANK RAYA - AZIMUTT ADMIN PASSWORD SETTER")
    print("Zero-Credential-Exposure Architecture")
    print("=" * 60)

    # d. Email admin dibaca dari argumen CLI atau variabel lingkungan AZIMUTT_ADMIN_EMAIL
    email = None
    if len(sys.argv) > 1 and sys.argv[1].strip():
        email = sys.argv[1].strip()
    elif os.environ.get("AZIMUTT_ADMIN_EMAIL", "").strip():
        email = os.environ.get("AZIMUTT_ADMIN_EMAIL", "").strip()
    else:
        try:
            inp = input("Masukkan email admin: ").strip()
            if inp:
                email = inp
        except (KeyboardInterrupt, EOFError):
            print("\n[INFO] Dibatalkan oleh pengguna.")
            sys.exit(1)

    if not email:
        print("[ERROR] Email admin harus ditentukan via argumen, AZIMUTT_ADMIN_EMAIL, atau input.")
        sys.exit(1)

    try:
        pw1 = getpass.getpass("Masukkan kata sandi baru: ")
        if not pw1:
            print("[ERROR] Kata sandi tidak boleh kosong.")
            sys.exit(1)

        # c. Tolak password > 72 byte (batas bcrypt) dan < 12 karakter, dengan pesan jelas
        pw_bytes = pw1.encode("utf-8")
        if len(pw1) < 12:
            print(f"[ERROR] Kata sandi terlalu pendek ({len(pw1)} karakter). Minimal 12 karakter.")
            sys.exit(1)
        if len(pw_bytes) > 72:
            print(f"[ERROR] Kata sandi melebihi batas bcrypt ({len(pw_bytes)} byte). Maksimal 72 byte.")
            sys.exit(1)

        pw2 = getpass.getpass("Konfirmasi kata sandi baru: ")
        if pw1 != pw2:
            print("[ERROR] Konfirmasi kata sandi tidak cocok.")
            sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("\n[INFO] Dibatalkan oleh pengguna.")
        sys.exit(1)

    # Hash with bcrypt (12 rounds)
    pw_hash = bcrypt.hashpw(pw_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")
    del pw1, pw2, pw_bytes

    docker_bin = find_docker_bin()

    # e. Tidak ada f-string yang menaruh input pengguna ke SQL; email dilewatkan via psql variable
    sql = f"""
    UPDATE users
    SET hashed_password = '{pw_hash}', updated_at = NOW()
    WHERE email = :'admin_email';
    """

    # a. psql dipanggil dengan -v ON_ERROR_STOP=1
    psql_args = [
        "psql", "-U", "azimutt_bank_admin", "-d", "azimutt_metadata",
        "-v", "ON_ERROR_STOP=1",
        "-v", f"admin_email={email}"
    ]

    if docker_bin.startswith("wsl") or not shutil.which(docker_bin):
        cmd = ["wsl", "-d", "Ubuntu", "-e", "docker", "exec", "-i", "azimutt-backend-db"] + psql_args
    else:
        test = subprocess.run([docker_bin, "info"], capture_output=True, check=False)
        if test.returncode != 0:
            cmd = ["wsl", "-d", "Ubuntu", "-e", "docker", "exec", "-i", "azimutt-backend-db"] + psql_args
        else:
            cmd = [docker_bin, "exec", "-i", "azimutt-backend-db"] + psql_args

    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    del pw_hash

    # a. Stderr disaring agar tidak pernah mencetak hash mentah, maksimal 3 baris
    if res.stderr:
        cleaned_err = re.sub(r'\$2[aby]\$\d\d\$\S+', '***', res.stderr)
        err_lines = cleaned_err.strip().splitlines()[:3]
        if res.returncode != 0:
            print("[ERROR] Database melaporkan error:")
            for l in err_lines:
                print(f"  {l}")

    # b. Pastikan UPDATE mengembalikan 'UPDATE 1' (parse stdout)
    stdout_text = res.stdout.strip() if res.stdout else ""
    if res.returncode == 0 and "UPDATE 1" in stdout_text:
        print("[PASS] Kata sandi admin berhasil diperbarui di database PostgreSQL metadata.")
    else:
        if res.returncode == 0 and "UPDATE 0" in stdout_text:
            print(f"[ERROR] Tidak ada pengguna yang cocok dengan email: {email}")
        else:
            print("[ERROR] Gagal memperbarui kata sandi di PostgreSQL.")
        sys.exit(1)

if __name__ == "__main__":
    main()
