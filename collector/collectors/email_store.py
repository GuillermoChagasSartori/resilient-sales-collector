"""Collector for the store that emails its numbers in.

fetch() reads a saved .eml here; in production it is an IMAP search for the
day's message from that sender. parse() is identical either way, which is the
point of keeping the two steps apart.
"""

from __future__ import annotations

import re
from datetime import datetime
from email import message_from_string
from email.message import Message

from ..base import Collector
from ..errors import ParseError
from ..models import SalesRow

SUBJECT_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
# The manager types the numbers as a pipe-separated list. Tolerant of spacing,
# strict about shape -- anything else is reported rather than silently skipped.
LINE_ITEM = re.compile(
    r"^\s*(?P<sku>[A-Z]{3}-\d{4})\s*\|\s*(?P<product>[^|]+?)\s*\|\s*(?P<category>[^|]+?)"
    r"\s*\|\s*(?P<quantity>\d+(?:\.\d+)?)\s*\|\s*(?P<unit_price>\d+(?:\.\d+)?)\s*$"
)


class EmailReportCollector(Collector):
    type_name = "email_report"

    def parse(self, raw: str) -> list[SalesRow]:
        message = message_from_string(raw)
        subject = message.get("Subject", "")
        date_match = SUBJECT_DATE.search(subject)
        if not date_match:
            raise ParseError(f"no date (YYYY-MM-DD) in the email subject: {subject!r}")
        sale_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()

        rows: list[SalesRow] = []
        for line in self._body(message).splitlines():
            match = LINE_ITEM.match(line)
            if not match:
                continue  # greetings, signature, quoted replies
            rows.append(
                SalesRow(
                    store_id=self.store.id,
                    store_name=self.store.name,
                    sale_date=sale_date,
                    sku=match["sku"],
                    product=match["product"],
                    category=match["category"].lower(),
                    quantity=float(match["quantity"]),
                    unit_price=float(match["unit_price"]),
                )
            )

        if not rows:
            raise ParseError(
                "email body contained no recognisable line items "
                "(expected 'SKU-0000 | product | category | qty | price')"
            )
        return rows

    @staticmethod
    def _body(message: Message) -> str:
        if not message.is_multipart():
            return message.get_payload(decode=False)
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=False)
        raise ParseError("email has no text/plain part")
