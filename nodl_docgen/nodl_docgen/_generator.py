"""Generate RST documentation from a NodlDocument."""
from __future__ import annotations

from typing import List, Optional, Tuple

from nodl.models import NodlDocument, QoS


def _qos_str(qos: Optional[QoS]) -> str:
    if qos is None:
        return 'default'
    parts = []
    parts.append('Reliable' if qos.reliability == 'RELIABLE' else 'Best effort')
    if qos.history == 'ALL':
        parts.append('keep all')
    else:
        parts.append(f'depth {qos.history}')
    if qos.durability == 'TRANSIENT_LOCAL':
        parts.append('transient local')
    return ' · '.join(parts)


def _list_table(
    headers: List[str],
    rows: List[Tuple[str, ...]],
    widths: Optional[List[int]] = None,
    title: str = '',
) -> str:
    if widths is None:
        w = 100 // len(headers)
        widths = [w] * len(headers)

    lines = [f'.. list-table:: {title}' if title else '.. list-table::']
    lines.append('   :header-rows: 1')
    lines.append(f'   :widths: {" ".join(str(w) for w in widths)}')
    lines.append('')

    lines.append(f'   * - {headers[0]}')
    for h in headers[1:]:
        lines.append(f'     - {h}')

    for row in rows:
        lines.append(f'   * - {row[0]}')
        for cell in row[1:]:
            lines.append(f'     - {cell}')

    return '\n'.join(lines)


def _section(title: str, underline_char: str = '-') -> str:
    return f'{title}\n{underline_char * len(title)}'


def generate_rst(doc: NodlDocument) -> str:
    """Return a complete RST document describing the node interfaces."""
    node_name = (doc.node.name if doc.node else None) or 'node'
    parts: List[str] = []

    parts.append(node_name)
    parts.append('=' * len(node_name))
    parts.append('')

    if doc.publishers:
        parts.append(_section('Publishers'))
        parts.append('')
        rows = [
            (f'``{p.topic}``', f'``{p.type}``', _qos_str(p.qos))
            for p in doc.publishers
        ]
        parts.append(_list_table(['Topic', 'Type', 'QoS'], rows, [35, 40, 25]))
        parts.append('')

    if doc.subscriptions:
        parts.append(_section('Subscriptions'))
        parts.append('')
        rows = [
            (f'``{s.topic}``', f'``{s.type}``', _qos_str(s.qos))
            for s in doc.subscriptions
        ]
        parts.append(_list_table(['Topic', 'Type', 'QoS'], rows, [35, 40, 25]))
        parts.append('')

    if doc.parameters:
        parts.append(_section('Parameters'))
        parts.append('')
        rows = []
        for name, param in doc.parameters.items():
            default = f'``{param.default_value}``' if param.default_value is not None else ''
            desc = param.description or ''
            if param.read_only:
                desc = (desc + ' *(read-only)*').lstrip()
            rows.append((f'``{name}``', f'``{param.type}``', default, desc))
        parts.append(_list_table(
            ['Name', 'Type', 'Default', 'Description'],
            rows,
            [25, 15, 20, 40],
        ))
        parts.append('')

    if doc.service_servers:
        parts.append(_section('Service Servers'))
        parts.append('')
        rows = [
            (f'``{s.name}``', f'``{s.type}``', s.description or '')
            for s in doc.service_servers
        ]
        parts.append(_list_table(['Service', 'Type', 'Description'], rows, [35, 40, 25]))
        parts.append('')

    if doc.service_clients:
        parts.append(_section('Service Clients'))
        parts.append('')
        rows = [
            (f'``{c.name}``', f'``{c.type}``', c.description or '')
            for c in doc.service_clients
        ]
        parts.append(_list_table(['Service', 'Type', 'Description'], rows, [35, 40, 25]))
        parts.append('')

    if doc.action_servers:
        parts.append(_section('Action Servers'))
        parts.append('')
        rows = [
            (f'``{a.name}``', f'``{a.type}``', a.description or '')
            for a in doc.action_servers
        ]
        parts.append(_list_table(['Action', 'Type', 'Description'], rows, [35, 40, 25]))
        parts.append('')

    if doc.action_clients:
        parts.append(_section('Action Clients'))
        parts.append('')
        rows = [
            (f'``{a.name}``', f'``{a.type}``', a.description or '')
            for a in doc.action_clients
        ]
        parts.append(_list_table(['Action', 'Type', 'Description'], rows, [35, 40, 25]))
        parts.append('')

    return '\n'.join(parts)
