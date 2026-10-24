"""Response-language preference for the Korea event branch."""

RESPONSE_LANGUAGE = (
    'Korea demo language: use natural, concise Korean by default for attendee-facing prose, '
    'including chat, Mission Control summaries, assignments, reasons, handoffs, final answers '
    'and generated webpage text. English internal instructions, role names or source material '
    'do not change this default. Honor an explicit user request for another language for the '
    'requested content. Preserve code, commands, identifiers, paths, URLs and exact quotations. '
    'In structured responses, keep JSON keys, control values and required markers unchanged; '
    'write human-readable string values in Korean. Keep the required output format; add no '
    'prose outside a JSON-only response.'
)
