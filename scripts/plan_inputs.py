"""Task-scoped input snapshots, never a blanket copy of a personal workspace."""
import re


EVENT_INTERNAL_INPUTS = {'handoffs.md', 'shared-brief.json'}


class PlanInputError(RuntimeError):
    """Invalid model-selected documents, before any specialist is dispatched."""


def internal_team_input(path):
    name = path.rsplit('/', 1)[-1]
    return name in EVENT_INTERNAL_INPUTS or bool(re.match(r'^(?:plan-input|plan|chat)-[0-9a-f]{24}(?:-|\.)', name))


def requested_inputs(studio, origin, task):
    from studio import safe_file, Problem
    from document_upload import MAX_FILE
    base = studio.workspace(origin['owner'], origin.get('role'))
    folder = base / 'inbox'
    if base.is_symlink() or folder.is_symlink() or not folder.is_dir():
        return []
    # Generic upload references apply only to a personal inbox. Team inboxes also
    # contain event contracts, so require an explicit filename there.
    uploaded = origin.get('role') is None and re.search(
        r'\b(uploaded|attached|supplied)\b|업로드|첨부|올린|올려둔', task, re.I)
    inputs, total = [], 0
    for path in sorted(folder.iterdir()):
        if origin.get('role') is not None and internal_team_input(path.name):
            continue
        if path.suffix.lower() not in ('.txt', '.md', '.csv', '.pdf', '.pptx', '.xlsx'):
            continue
        # Exclude generated handoff snapshots, not user names such as plan-notes.md.
        if re.match(r'^(?:plan-input|plan|chat)-[0-9a-f]{24}(?:-|\.)', path.name):
            continue
        if path.name.lower().endswith(('.pdf.txt', '.pptx.txt', '.xlsx.txt')) and path.with_suffix('').exists():
            continue
        named = re.search(r'(?<![\w.-])' + re.escape(path.name) + r'(?![\w-]|\.\w)', task, re.I)
        if not (named or uploaded):
            continue
        source = safe_file(base, 'inbox/' + path.name, True)
        # Prefer extracted text for binary documents. Never claim this captures
        # omitted images, formulas or formatting.
        extracted = path.suffix.lower() in ('.pdf', '.pptx', '.xlsx')
        if extracted:
            source = safe_file(base, 'inbox/' + path.name + '.txt', True)
        raw = source.read_bytes()
        total += len(raw)
        if len(raw) > MAX_FILE or total > 30 * 1024 * 1024 or len(inputs) >= 10:
            raise Problem('Too many document inputs for one /goal. Name up to 10 files totaling 30 MB or less.')
        inputs.append({'id': 'document-' + str(len(inputs)), 'name': path.name,
                       'extractedText': extracted, 'suffix': source.suffix, 'data': raw})
    return inputs


def input_manifest(inputs):
    return [{key: item[key] for key in ('id', 'name', 'extractedText')} for item in inputs]


def validate_assignments(tasks, available, has_images):
    from plan_handoff import required_files
    allowed = {item['id'] for item in available}
    earlier_outputs = set()
    for task in tasks:
        if 'inputs' not in task:
            # Some models mention the provided document ID in their assignment
            # but omit the structured field. Resolve only those exact IDs from
            # the already user-scoped manifest, never the entire inbox.
            text = task.get('task', '') + '\n' + task.get('expected', '')
            task['inputs'] = [item['id'] for item in available
                              if re.search(r'(?<![\w-])' + re.escape(item['id']) + r'(?![\w-])', text)]
        # Models sometimes put planned handoff paths in the upload selector.
        # Only exact outputs declared by an EARLIER assignment are handoffs;
        # never resolve arbitrary paths or inspect existing workspace files.
        selected = task.get('inputs', [])
        if any(key not in allowed and key not in earlier_outputs for key in selected):
            raise PlanInputError('The Captain selected an unavailable document. No specialist was started.')
        if task.get('useImages') and not has_images:
            raise RuntimeError('The Captain selected images that were not attached. No specialist was started.')
        task['inputs'] = [key for key in selected if key in allowed]
        # Execution already verifies required outputs before the next turn and
        # copies collected artifacts through the job-scoped handoff mapping.
        earlier_outputs.update(required_files(task))
