import {
  IDataObject,
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

const ALL_PLATFORMS = [
  { name: 'Twitter / X', value: 'twitter' },
  { name: 'Bluesky', value: 'bluesky' },
  { name: 'Telegram', value: 'telegram' },
  { name: 'Instagram', value: 'instagram' },
  { name: 'LinkedIn', value: 'linkedin' },
  { name: 'Threads', value: 'threads' },
];

/**
 * Open-Dispatch n8n node.
 *
 * Operations
 *  - Dispatch:    POST /dispatch — send content to selected platforms.
 *  - Adapt:       POST /ai/adapt — rewrite a caption per-platform.
 *  - Get Row:     GET /queue/{id} — fetch one queue row (JSON).
 *  - Retry Row:   POST /queue/{id}/retry — re-queue a failed row.
 *  - List Queue:  GET /queue?status=… — list queue rows.
 *
 * All operations use the OpenDispatchApi credential, which carries the
 * base URL and (optional) bearer token for proxied setups.
 */
export class OpenDispatch implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'Open-Dispatch',
    name: 'openDispatch',
    icon: 'file:opendispatch.svg',
    group: ['transform'],
    version: 1,
    subtitle: '={{ $parameter["operation"] + ": " + ($parameter["resource"] || "") }}',
    description: 'Cross-post to Twitter, Bluesky, Telegram, Instagram, LinkedIn, Threads via Open-Dispatch.',
    defaults: { name: 'Open-Dispatch' },
    // NodeConnectionType is a type alias to "main" string in n8n-workflow
    inputs: ['main'],
    outputs: ['main'],
    credentials: [{ name: 'openDispatchApi', required: true }],
    requestDefaults: {
      baseURL: '={{ $credentials.baseUrl }}',
      headers: { 'Content-Type': 'application/json' },
    },
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        options: [
          { name: 'Dispatch (post now / scheduled)', value: 'dispatch', action: 'Dispatch content' },
          { name: 'Adapt Caption with AI', value: 'adapt', action: 'Adapt caption' },
          { name: 'Get Queue Row', value: 'getRow', action: 'Get queue row' },
          { name: 'Retry Queue Row', value: 'retryRow', action: 'Retry queue row' },
          { name: 'List Queue', value: 'listQueue', action: 'List queue' },
        ],
        default: 'dispatch',
      },

      // ───────────── Dispatch ─────────────
      {
        displayName: 'Platforms',
        name: 'platforms',
        type: 'multiOptions',
        displayOptions: { show: { operation: ['dispatch', 'adapt'] } },
        options: ALL_PLATFORMS,
        default: ['twitter', 'bluesky'],
        description: 'Pick which platforms receive this post. Use Account Override for non-default accounts.',
      },
      {
        displayName: 'Account Override',
        name: 'accountOverride',
        type: 'string',
        displayOptions: { show: { operation: ['dispatch'] } },
        default: '',
        placeholder: 'twitter:work,bluesky:personal',
        description: 'Comma-separated targets — overrides the Platforms selection when set.',
      },
      {
        displayName: 'Text',
        name: 'text',
        type: 'string',
        typeOptions: { rows: 4 },
        displayOptions: { show: { operation: ['dispatch', 'adapt'] } },
        default: '',
        description: 'Caption text. Used for every selected platform unless Formats JSON is set.',
        required: true,
      },
      {
        displayName: 'Schedule For (ISO-8601)',
        name: 'scheduledFor',
        type: 'string',
        displayOptions: { show: { operation: ['dispatch'] } },
        default: '',
        placeholder: '2026-05-21T12:00:00+00:00',
        description: 'Leave blank to publish immediately.',
      },
      {
        displayName: 'Webhook URL',
        name: 'webhookUrl',
        type: 'string',
        displayOptions: { show: { operation: ['dispatch'] } },
        default: '',
        placeholder: 'https://your-app.example/dispatch-callback',
        description: 'Open-Dispatch fires a POST here on publish or fail. Leave blank to skip.',
      },
      {
        displayName: 'Use AI Adapter',
        name: 'useAdapter',
        type: 'boolean',
        displayOptions: { show: { operation: ['dispatch'] } },
        default: false,
        description: 'Whether to rewrite the text per-platform via /ai/adapt before enqueueing.',
      },
      {
        displayName: 'Formats JSON (advanced)',
        name: 'formatsJson',
        type: 'json',
        displayOptions: { show: { operation: ['dispatch'] } },
        default: '',
        description: 'Overrides Text + AI adapter. Use to attach images, build threads, etc.',
      },

      // ───────────── Adapt ─────────────
      {
        displayName: 'Provider',
        name: 'provider',
        type: 'options',
        displayOptions: { show: { operation: ['adapt'] } },
        options: [
          { name: 'Auto (Ollama if available, else OpenRouter, else heuristic)', value: '' },
          { name: 'OpenRouter', value: 'openrouter' },
          { name: 'Ollama (local)', value: 'ollama' },
          { name: 'Heuristic (no LLM)', value: 'heuristic' },
        ],
        default: '',
      },

      // ───────────── Queue ops ─────────────
      {
        displayName: 'Row ID',
        name: 'rowId',
        type: 'string',
        displayOptions: { show: { operation: ['getRow', 'retryRow'] } },
        default: '',
        required: true,
        description: 'UUID of the queue row.',
      },
      {
        displayName: 'Status Filter',
        name: 'statusFilter',
        type: 'options',
        displayOptions: { show: { operation: ['listQueue'] } },
        options: [
          { name: 'All', value: '' },
          { name: 'Queued', value: 'queued' },
          { name: 'Publishing', value: 'publishing' },
          { name: 'Published', value: 'published' },
          { name: 'Failed', value: 'failed' },
          { name: 'Dead', value: 'dead' },
        ],
        default: '',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const out: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      const operation = this.getNodeParameter('operation', i) as string;

      try {
        if (operation === 'dispatch') {
          const platforms = this.getNodeParameter('platforms', i) as string[];
          const accountOverride = (this.getNodeParameter('accountOverride', i, '') as string).trim();
          const text = this.getNodeParameter('text', i) as string;
          const scheduledFor = (this.getNodeParameter('scheduledFor', i, '') as string).trim();
          const webhookUrl = (this.getNodeParameter('webhookUrl', i, '') as string).trim();
          const useAdapter = this.getNodeParameter('useAdapter', i, false) as boolean;
          const formatsJsonRaw = this.getNodeParameter('formatsJson', i, '') as string;

          const targets =
            accountOverride.length > 0
              ? accountOverride.split(',').map(t => t.trim()).filter(Boolean)
              : platforms;
          if (targets.length === 0) {
            throw new NodeOperationError(this.getNode(), 'Pick at least one platform or set Account Override');
          }

          let formats: Record<string, unknown> = {};
          if (formatsJsonRaw && typeof formatsJsonRaw === 'string' && formatsJsonRaw.trim().length > 0) {
            formats = JSON.parse(formatsJsonRaw) as Record<string, unknown>;
          } else if (useAdapter) {
            const adapted = await this.helpers.httpRequestWithAuthentication.call(this, 'openDispatchApi', {
              method: 'POST',
              url: '/ai/adapt',
              body: { text, platforms: platforms.length > 0 ? platforms : targets.map(t => t.split(':')[0]) },
              json: true,
            });
            formats = (adapted as { formats: Record<string, unknown> }).formats;
          } else {
            formats = buildDefaultFormats(text, targets);
          }

          const body: Record<string, unknown> = {
            category: 'n8n',
            targets,
            formats,
          };
          if (scheduledFor) body.scheduled_for = scheduledFor;
          if (webhookUrl) body.webhook_url = webhookUrl;

          const resp = await this.helpers.httpRequestWithAuthentication.call(this, 'openDispatchApi', {
            method: 'POST',
            url: '/dispatch',
            body,
            json: true,
          });
          out.push({ json: resp as IDataObject, pairedItem: { item: i } });

        } else if (operation === 'adapt') {
          const platforms = this.getNodeParameter('platforms', i) as string[];
          const text = this.getNodeParameter('text', i) as string;
          const provider = (this.getNodeParameter('provider', i, '') as string) || undefined;
          const body: Record<string, unknown> = { text, platforms };
          if (provider) body.provider = provider;
          const resp = await this.helpers.httpRequestWithAuthentication.call(this, 'openDispatchApi', {
            method: 'POST',
            url: '/ai/adapt',
            body,
            json: true,
          });
          out.push({ json: resp as IDataObject, pairedItem: { item: i } });

        } else if (operation === 'getRow') {
          const rowId = this.getNodeParameter('rowId', i) as string;
          const resp = await this.helpers.httpRequestWithAuthentication.call(this, 'openDispatchApi', {
            method: 'GET',
            url: `/queue/${encodeURIComponent(rowId)}`,
            headers: { Accept: 'application/json' },
            json: true,
          });
          out.push({ json: resp as IDataObject, pairedItem: { item: i } });

        } else if (operation === 'retryRow') {
          const rowId = this.getNodeParameter('rowId', i) as string;
          const resp = await this.helpers.httpRequestWithAuthentication.call(this, 'openDispatchApi', {
            method: 'POST',
            url: `/queue/${encodeURIComponent(rowId)}/retry`,
            headers: { Accept: 'application/json' },
            json: true,
          });
          out.push({ json: resp as IDataObject, pairedItem: { item: i } });

        } else if (operation === 'listQueue') {
          const statusFilter = (this.getNodeParameter('statusFilter', i, '') as string) || '';
          const url = statusFilter ? `/queue?status=${encodeURIComponent(statusFilter)}` : '/queue';
          const resp = await this.helpers.httpRequestWithAuthentication.call(this, 'openDispatchApi', {
            method: 'GET',
            url,
            json: true,
          });
          out.push({ json: resp as IDataObject, pairedItem: { item: i } });

        } else {
          throw new NodeOperationError(this.getNode(), `Unknown operation: ${operation}`);
        }
      } catch (err) {
        if (this.continueOnFail()) {
          out.push({ json: { error: (err as Error).message }, pairedItem: { item: i } });
          continue;
        }
        throw err;
      }
    }

    return [out];
  }
}

/**
 * Default per-platform formats when the user just supplies text and isn't
 * using the AI adapter. Mirrors the Python `_build_formats` helper.
 */
function buildDefaultFormats(text: string, targets: string[]): Record<string, unknown> {
  const formats: Record<string, unknown> = {};
  for (const target of targets) {
    const platform = target.split(':')[0];
    switch (platform) {
      case 'telegram':
        formats.telegram_message = { text };
        break;
      case 'twitter':
        formats.twitter_thread = { tweets: [text] };
        break;
      case 'bluesky':
        formats.bluesky_post = { text };
        break;
      case 'instagram':
        formats.instagram_post = { caption: text };
        break;
      case 'linkedin':
        formats.linkedin_post = { text };
        break;
      case 'threads':
        formats.threads_post = { text };
        break;
    }
  }
  return formats;
}
