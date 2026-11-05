// SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
// SPDX-License-Identifier: Apache-2.0
// Exercise the actual YAML Language Server language service without a GUI or network.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const { getLanguageService } = require('yaml-language-server/lib/umd/languageservice/yamlLanguageService');
const { TextDocument } = require('vscode-languageserver-textdocument');

const root = path.resolve(__dirname, '../..');
const read = (relative) => readFileSync(path.join(root, relative), 'utf8');
const settings = JSON.parse(read('tools/editor/examples/settings.json'));
const schemas = Object.entries(settings['yaml.schemas']).map(([uri, fileMatch]) => ({ uri, fileMatch }));
const base = schemas[0].uri.slice(0, schemas[0].uri.lastIndexOf('/') + 1);
const requested = new Set();
const service = getLanguageService({
  schemaRequestService: async (uri) => {
    assert.ok([`${base}nodl.schema.json`, `${base}parameter.schema.json`].includes(uri), `Unexpected schema: ${uri}`);
    requested.add(uri);
    return read(`nodl_schema/nodl_schema/schemas/${uri.slice(base.length)}`);
  },
  workspaceContext: { resolveRelativePath: (relative, resource) => new URL(relative, resource).href },
});
service.configure({ validate: true, completion: true, hover: true, schemas });
let version = 0;
const document = (text, filename = 'example.nodl.yaml') =>
  TextDocument.create(`file:///workspace/${filename}`, 'yaml', ++version, text);

for (const filename of ['example.nodl.yaml', 'example.nodl.yml', 'nodes/example.nodl.yaml', 'nodes/example.nodl.yml']) {
  test(`settings associate ${filename} and resolve parameter references`, async () => {
    assert.deepEqual(await service.doValidation(document(read('tools/editor/examples/valid.nodl.yaml'), filename)), []);
    const diagnostics = await service.doValidation(document(read('tools/editor/examples/invalid.nodl.yml'), filename));
    for (const line of [2, 5, 9]) {
      assert.ok(diagnostics.some((item) => item.range.start.line === line), JSON.stringify(diagnostics));
    }
    assert.ok(requested.has(`${base}parameter.schema.json`));
  });
}

test('ordinary YAML files have no NoDL association', async () => {
  assert.deepEqual(await service.doValidation(document('unrelated: true\n', 'ordinary.yaml')), []);
});

for (const [name, text, expected] of [
  ['root fields', 'nodl_version: 2\n', ['parameters', 'publishers', 'include']],
  ['parameter fields', 'nodl_version: 2\nparameters:\n  speed:\n    ', ['type', 'default_value', 'description']],
  ['parameter types', 'nodl_version: 2\nparameters:\n  speed:\n    type: ', ['double', 'int', 'byte_array']],
  ['QoS enums', 'nodl_version: 2\npublishers:\n  - name: /cmd_vel\n    type: geometry_msgs/msg/Twist\n    qos:\n      reliability: ', ['RELIABLE', 'BEST_EFFORT']],
]) {
  test(`completion suggests ${name}`, async () => {
    const doc = document(text);
    const result = await service.doComplete(doc, doc.positionAt(text.length), false);
    const labels = result.items.map((item) => item.label.replace(/^"|"$/g, ''));
    for (const label of expected) assert.ok(labels.includes(label), `${label} missing from ${labels}`);
  });
}

test('hover shows canonical field documentation', async () => {
  const hover = await service.doHover(document(read('tools/editor/examples/valid.nodl.yaml')), { line: 1, character: 5 });
  assert.match(JSON.stringify(hover), /NoDL schema major version/);
});
