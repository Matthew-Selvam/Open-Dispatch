// n8n community node entry point.
//
// package.json "main" points here. n8n itself loads nodes via the
// `n8n.nodes` field (dist/…), but a missing main would break plain
// require()/import() of the package — e.g. `npm link` smoke tests or
// programmatic node discovery — so re-export the compiled node here.

const { OpenDispatch } = require('./dist/nodes/OpenDispatch/OpenDispatch.node.js');

module.exports = { OpenDispatch };
