"""Disposable volume test. All data resides in a temporary directory.

Simulates 10,000 lots, 100,000 payments and five authenticated sessions.
Reports actual measurements without claiming hardware equivalence.
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def resident_mb(pid):
    import psutil

    process = psutil.Process(pid)
    return round(
        sum(
            p.memory_info().rss
            for p in [process, *process.children(recursive=True)]
            if p.is_running()
        )
        / 1024**2,
        2,
    )


def main():
    import httpx

    with tempfile.TemporaryDirectory(prefix="gestor-volume-") as directory:
        os.environ["GESTOR_DATA_DIR"] = directory
        from backend import db as database

        database.DATA = Path(directory)
        from backend.app import HASHER
        from backend.db import initialize, now, transaction

        initialize()
        with transaction() as db:
            db.execute(
                "INSERT INTO users VALUES(1,'benchmark','Benchmark',?,'superuser',1,0,?,NULL,0,NULL)",
                (HASHER.hash("BenchmarkSintetico123!"), now()),
            )
            db.execute(
                "INSERT INTO entities(id,name,currency) VALUES(1,'Escenario sintético','HNL')"
            )
            db.executemany(
                "INSERT INTO clients(id,entity_id,name,document_type,document,phone,created_by,created_at) VALUES(?,1,?,'DEMO',?,'000',1,?)",
                ((i, f"Cliente {i}", f"DEMO-{i}", now()) for i in range(1, 10001)),
            )
            db.executemany(
                "INSERT INTO lots(id,entity_id,code,price,currency,status) VALUES(?,1,?,10000000,'HNL','sold')",
                ((i, f"L-{i:05}") for i in range(1, 10001)),
            )
            db.executemany(
                "INSERT INTO contracts(id,entity_id,lot_id,client_id,price,currency,down_payment,installments,down_due,first_due,created_by,created_at) VALUES(?,1,?,?,10000000,'HNL',0,1,'2026-01-01','2026-01-01',1,?)",
                ((i, i, i, now()) for i in range(1, 10001)),
            )
            db.executemany(
                "INSERT INTO obligations(id,contract_id,number,due_date,amount,paid) VALUES(?,?,1,'2026-01-01',10000000,1000000)",
                ((i, i) for i in range(1, 10001)),
            )
            db.executemany(
                "INSERT INTO obligations(contract_id,number,due_date,amount,paid) VALUES(?,0,'2026-01-01',0,0)",
                ((i,) for i in range(1, 10001)),
            )
            for start in range(1, 100001, 1000):
                batch = [(i, (i - 1) % 10000 + 1) for i in range(start, start + 1000)]
                db.executemany(
                    "INSERT INTO payments(id,entity_id,contract_id,client_id,operation_id,request_hash,payment_date,received,received_currency,applied,method,created_by,created_at,balance_after) VALUES(?,1,?,?,?,?,'2026-09-01',100000,'HNL',100000,'cash',1,?,?)",
                    (
                        (
                            i,
                            c,
                            c,
                            f"benchmark-{i:016}",
                            hashlib.sha256(str(i).encode()).hexdigest(),
                            now(),
                            10000000 - (((i - 1) // 10000) + 1) * 100000,
                        )
                        for i, c in batch
                    ),
                )
                db.executemany(
                    "INSERT INTO allocations VALUES(?,?,100000)", ((i, c) for i, c in batch)
                )
                db.executemany(
                    "INSERT INTO receipts(payment_id,entity_id,year,number,folio,snapshot) VALUES(?,1,2026,?,?,?)",
                    ((i, i, f"REC-2026-{i:05}", json.dumps({"synthetic": True})) for i, c in batch),
                )
                db.executemany(
                    "INSERT INTO audit(created_at,user_id,role,entity_id,action,record_type,record_id) VALUES(?,1,'superuser',1,'create_payment','payment',?)",
                    ((now(), i) for i, c in batch),
                )
            db.execute("INSERT INTO receipt_sequences VALUES(1,2026,100000)")
        environment = {**os.environ, "GESTOR_DATA_DIR": directory}
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8019",
                "--no-access-log",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            url = "http://127.0.0.1:8019"
            for _ in range(100):
                try:
                    if httpx.get(url + "/api/status").status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            sessions = [httpx.Client(base_url=url, timeout=30) for _ in range(5)]
            for session in sessions:
                result = session.post(
                    "/api/auth/login",
                    json={"username": "benchmark", "password": "BenchmarkSintetico123!"},
                ).json()
                session.headers["X-CSRF-Token"] = result["csrf"]
            # Generate the first daily snapshot before timing routine requests.
            sessions[0].get("/api/entities").raise_for_status()
            memory_start = resident_mb(process.pid)
            results = {}
            for endpoint in (
                "/api/entities/1/clients?page=100",
                "/api/entities/1/payments?page=100",
                "/api/entities/1/contracts?page=100",
                "/api/entities/1/arrears?page=100",
                "/api/dashboard?entity=1",
            ):

                def query(session):
                    started = time.perf_counter()
                    response = session.get(endpoint)
                    response.raise_for_status()
                    return round((time.perf_counter() - started) * 1000, 2)

                with ThreadPoolExecutor(max_workers=5) as pool:
                    values = list(pool.map(query, sessions))
                results[endpoint] = {"ms": values, "max_ms": max(values)}

            # Real API collection includes PDF; direct financial timing below excludes it.
            def collect(pair):
                index, session = pair
                begin = time.perf_counter()
                response = session.post(
                    "/api/payments",
                    json={
                        "contract_id": index + 1,
                        "operation_id": f"volume-payment-{index:016}",
                        "amount": "1",
                        "currency": "HNL",
                    },
                )
                response.raise_for_status()
                return round((time.perf_counter() - begin) * 1000, 2)

            with ThreadPoolExecutor(max_workers=5) as pool:
                payment_ms = list(pool.map(collect, enumerate(sessions)))
            memory_end = resident_mb(process.pid)
            for session in sessions:
                session.close()
            report = {
                "date": str(date.today()),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "scenario": {"lots": 10000, "payments": 100000, "sessions": 5},
                "queries": results,
                "payment_including_pdf_ms": payment_ms,
                "backend_resident_mb_before": memory_start,
                "backend_resident_mb_after": memory_end,
                "note": "Equipo anfitrión actual; no equivale a validación en Windows 10 con 4 GB RAM y SSD.",
            }
            (ROOT / "docs").mkdir(exist_ok=True)
            (ROOT / "docs" / "benchmark.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            print(json.dumps(report, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
