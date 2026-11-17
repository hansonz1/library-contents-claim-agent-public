"""Build a draft claim packet from browser-exported sweep evidence."""

import argparse
import base64
import json
from datetime import date, datetime
from decimal import Decimal
from html import escape
from pathlib import Path
from urllib.parse import urlsplit


def add_valuations(packet: dict, catalog: dict):
    sweep = packet["sweep"]
    if not sweep["country"] or not sweep["currency"] or any(
        catalog[key] != sweep[key] for key in ("country", "currency")
    ):
        raise ValueError("Valuation locale must match the sweep.")
    candidates = {entry["title"]: entry for entry in packet.get("inventory_candidates", [])}
    totals = {"replacement_cost": Decimal(0), "used_value": Decimal(0)}
    priced = set()
    for entry in catalog["books"]:
        title = entry["title"]
        if title in priced or title not in candidates:
            raise ValueError(f"Expected one valuation for a known candidate: {title}")
        prices = {}
        for kind in totals:
            price = entry[kind]
            amount = Decimal(str(price["amount"]))
            url = urlsplit(price["url"])
            date.fromisoformat(price["retrieved_at"])
            if (
                not amount.is_finite() or amount <= 0
                or amount != amount.quantize(Decimal("0.01"))
                or not price["source"].strip() or not price["condition_assumed"].strip()
                or url.scheme not in {"http", "https"} or not url.hostname
            ):
                raise ValueError(f"Invalid sourced price for {title}: {kind}")
            prices[kind] = {**price, "amount": float(amount), "converted": False}
            totals[kind] += amount
        priced.add(title)
        packet["books"].append({
            "id": f"book-{len(priced):03}", "title": title, "status": "identified",
            "frame_ref": candidates[title]["frame_refs"][0],
            "shelf": None, "position": None, "author": entry.get("author", ""),
            "edition": entry.get("edition", ""), "isbn": entry.get("isbn", ""),
            "spine_height_cm": None, "spine_thickness_cm": None, "id_confidence": None,
            **prices,
        })
    if not priced:
        return
    packet["totals"]["books_identified"] = len(priced)
    packet["totals"]["books_replacement_cost"] = float(totals["replacement_cost"])
    packet["totals"]["books_used_value"] = float(totals["used_value"])
    queue = packet["review_queue"]
    queue[:] = [entry for entry in queue if entry["ref_id"] != "valuation"]
    for title in candidates.keys() - priced:
        queue.append({"ref_id": candidates[title]["frame_refs"][0], "reason": f"No verified prices for {title}."})


def export_claim(evidence_path: Path, output: Path, country: str, currency: str, valuations: Path | None = None):
    evidence = json.loads(evidence_path.read_text())
    if not evidence["frames"]:
        raise ValueError("Sweep evidence contains no frames.")

    frames = []
    for number, frame in enumerate(evidence["frames"], start=1):
        prefix, _, data = frame["image"].partition(",")
        jpeg = base64.b64decode(data, validate=True)
        if prefix != "data:image/jpeg;base64" or not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
            raise ValueError(f"Invalid JPEG in frame {number}.")
        frames.append((f"frame-{number:03}.jpg", jpeg, frame.get("transcript")))

    start = evidence["started_at"]
    stop = evidence.get("stopped_at")
    duration = (datetime.fromisoformat(stop) - datetime.fromisoformat(start)).total_seconds() if stop else None
    review = [
        {"ref_id": "inventory", "reason": "Sweep feedback needs structured book and non-book identification."},
        {"ref_id": "room", "reason": "No calibrated room measurement available."},
        {"ref_id": "valuation", "reason": "No sourced valuation available."},
    ]
    packet = {
        "sweep": {
            "id": evidence["id"], "captured_at": start, "device": "",
            "duration_s": duration, "country": country, "currency": currency,
        },
        "room": {
            "length_m": None, "width_m": None, "height_m": None, "floor_area_m2": None,
            "wall_area_m2": None, "shelved_wall_area_m2": None, "scale_method": "", "confidence": None,
        },
        "books": [],
        "items": [],
        "totals": {
            "book_count": None, "books_identified": 0, "books_unidentified": 0,
            "shelf_run_m": None, "books_replacement_cost": None, "books_used_value": None,
            "items_replacement_cost_low": None, "items_replacement_cost_high": None,
            "excluded_from_totals": None,
        },
        "review_queue": review,
        "evidence": [{"frame_ref": name, "transcript": transcript} for name, _, transcript in frames],
    }
    voice = evidence.get("voice")
    if voice:
        reference = voice["frame_ref"]
        if not isinstance(reference, int) or not 1 <= reference <= len(frames):
            raise ValueError("Voice evidence references a missing frame.")
        packet["voice"] = {**voice, "frame_ref": frames[reference - 1][0]}
    inventory = evidence.get("inventory", [])
    if inventory:
        packet["inventory_candidates"] = [
            {
                "title": entry["title"],
                "frame_refs": [frames[number - 1][0] for number in entry["frames"]],
            }
            for entry in inventory
        ]
    if evidence.get("corrections"):
        packet["corrections"] = [
            {**entry, "frame_refs": [frames[number - 1][0] for number in entry["frames"]]}
            for entry in evidence["corrections"]
        ]
    for entry in evidence.get("review", []):
        review.append({"ref_id": frames[entry["frame"] - 1][0], "reason": entry["reason"]})
    if valuations is not None:
        add_valuations(packet, json.loads(valuations.read_text()))
    output.mkdir()
    for name, jpeg, _ in frames:
        (output / name).write_bytes(jpeg)
    (output / "claim_packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
    entries = "".join(
        f'<li><a href="{entry["frame_ref"]}">{entry["frame_ref"]}</a> '
        f'{escape(entry["transcript"] or "Feedback unavailable.")}</li>'
        for entry in packet["evidence"]
    )
    reviews = "".join(f'<li>{escape(entry["reason"])}</li>' for entry in packet["review_queue"])
    candidates = "".join(
        f'<li>{escape(entry["title"])} · ' +
        ", ".join(f'<a href="{name}">{name}</a>' for name in entry["frame_refs"]) + "</li>"
        for entry in packet.get("inventory_candidates", [])
    )
    inventory_section = f"<h2>Book title candidates</h2><ul>{candidates}</ul>" if candidates else ""
    price_section = ""
    if packet["books"]:
        lines = []
        for book in packet["books"]:
            links = []
            for kind, label in (("replacement_cost", "Replacement"), ("used_value", "Used")):
                price = book[kind]
                links.append(
                    f'{label} {price["amount"]:.2f} {escape(currency)} '
                    f'<a href="{escape(price["url"], quote=True)}">{escape(price["source"])}</a> '
                    f'({escape(price["retrieved_at"])}, {escape(price["condition_assumed"])})'
                )
            lines.append(f'<li>{escape(book["title"])} · ' + " · ".join(links) + "</li>")
        price_section = "<h2>Sourced book valuations</h2><ul>" + "".join(lines) + "</ul>"
    voice_section = ""
    if voice:
        reference = packet["voice"]["frame_ref"]
        voice_section = (
            f'<h2>Voice question</h2><p><a href="{reference}">{reference}</a></p>'
            f'<p>Heard: {escape(voice.get("heard") or "")}</p>'
            f'<p>Reply: {escape(voice.get("reply") or "")}</p>'
        )
    (output / "report.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        "<title>Draft claim packet</title><h1>Draft claim packet</h1>"
        f"<p>{escape(country)} · {escape(currency)}</p>"
        f"<h2>Capture evidence</h2><ol>{entries}</ol>{inventory_section}{price_section}{voice_section}"
        f"<h2>Review queue</h2><ul>{reviews}</ul>"
        '<p><a href="claim_packet.json">Claim packet JSON</a></p></html>\n'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path, help="A new output directory.")
    parser.add_argument("--country", required=True)
    parser.add_argument("--currency", required=True)
    parser.add_argument("--valuations", type=Path, help="Reviewed local book prices in JSON.")
    args = parser.parse_args()
    export_claim(args.evidence, args.output, args.country, args.currency, args.valuations)
