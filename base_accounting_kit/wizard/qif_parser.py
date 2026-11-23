# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
"""Dependency-free reader for QIF bank statements.

QIF (Quicken Interchange Format) is a plain-text format: every record is a
list of ``<code><value>`` lines terminated by a caret (``^``).  Only the
subset needed by the bank statement import wizard is understood here:

* Non-investment sections: ``!Type:Bank``, ``!Type:Cash``, ``!Type:Ccard``,
  ``!Type:Oth A``, ``!Type:Oth L`` and ``!Type:Invoice``.
* Transaction fields: ``D`` (date), ``T`` (amount), ``P`` (payee),
  ``M`` (memo), ``N`` (number) and ``L`` (category).

Account, category, class, memorized and investment sections are ignored
because the wizard does not consume them.  Dates and amounts are returned as
raw strings so the wizard can reuse its existing ``_parse_date`` and
``_parse_float`` helpers.
"""

#: Section headers that contain regular (non-investment) transactions.
TRANSACTION_HEADERS = frozenset({
    '!type:bank',
    '!type:cash',
    '!type:ccard',
    '!type:oth a',
    '!type:oth l',
    '!type:invoice',
})


class QifTransaction(object):
    """One QIF transaction, with the fields used by the import wizard."""

    __slots__ = ('date', 'amount', 'payee', 'memo', 'num', 'category')

    def __init__(self):
        self.date = None
        self.amount = None
        self.payee = None
        self.memo = None
        self.num = None
        self.category = None

    def __repr__(self):
        return '<QifTransaction %r %r %r>' % (
            self.date, self.amount, self.payee)


def _decode(data):
    """Decode raw QIF bytes, tolerating the encodings banks usually emit."""
    if isinstance(data, str):
        return data
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('latin-1', errors='replace')


def _normalize_date(value):
    """Normalize QIF date variants (``7/ 9'98``) without reordering parts.

    The component order is preserved because QIF exports may use either
    ``MM/DD/YYYY`` or ``DD/MM/YYYY``; ``_parse_date`` on the wizard resolves
    the final value.  Two-digit years are expanded using the usual Quicken
    pivot (00-69 -> 2000-2069, 70-99 -> 1970-1999).
    """
    value = value.strip().replace("'", '/')
    parts = [part.strip() for part in value.split('/')]
    if len(parts) != 3 or not all(parts):
        return value
    year = parts[2]
    if len(year) == 2 and year.isdigit():
        year_num = int(year)
        year = str(2000 + year_num if year_num < 70 else 1900 + year_num)
    parts[2] = year
    return '/'.join(part.zfill(2) if part.isdigit() else part
                    for part in parts)


def parse_qif(data):
    """Parse QIF content (``bytes`` or ``str``) into transactions.

    :param data: raw file content or already-decoded text.
    :return: list of :class:`QifTransaction` in file order.
    """
    text = _decode(data).lstrip('\ufeff')
    transactions = []
    current = None
    in_transactions = True

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('!'):
            in_transactions = line.lower() in TRANSACTION_HEADERS
            continue
        if not in_transactions:
            continue
        if line == '^':
            if current is not None:
                transactions.append(current)
                current = None
            continue

        code = line[0].upper()
        value = line[1:].strip()
        if code not in ('D', 'T', 'P', 'M', 'N', 'L'):
            # Cleared status, addresses, splits, ... are not consumed.
            continue
        if current is None:
            current = QifTransaction()
        if code == 'D':
            current.date = _normalize_date(value) or None
        elif code == 'T':
            current.amount = value
        elif code == 'P':
            current.payee = value or None
        elif code == 'M':
            current.memo = value or None
        elif code == 'N':
            current.num = value or None
        elif code == 'L':
            current.category = value or None

    # Tolerate a missing final caret at end of file.
    if current is not None:
        transactions.append(current)
    return transactions
