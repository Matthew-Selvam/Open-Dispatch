import {
  IAuthenticateGeneric,
  ICredentialTestRequest,
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

/**
 * Open-Dispatch credential.
 *
 * Open-Dispatch itself is unauthenticated by default (designed for trusted-
 * network self-hosting). When the user puts it behind a reverse proxy with
 * Basic auth or an API key header, this credential lets them pass that
 * along. The base URL is required, the auth fields are optional.
 */
export class OpenDispatchApi implements ICredentialType {
  name = 'openDispatchApi';
  displayName = 'Open-Dispatch';
  documentationUrl = 'https://github.com/matthewselvam/open-dispatch';
  properties: INodeProperties[] = [
    {
      displayName: 'Base URL',
      name: 'baseUrl',
      type: 'string',
      default: 'http://localhost:8000',
      placeholder: 'http://localhost:8000',
      description: 'URL of your Open-Dispatch instance.',
      required: true,
    },
    {
      displayName: 'API Key Header (optional)',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description:
        'If you front Open-Dispatch with a reverse proxy that requires a bearer token, enter it here.',
    },
  ];

  authenticate: IAuthenticateGeneric = {
    type: 'generic',
    properties: {
      headers: {
        Authorization: '={{ $credentials.apiKey ? "Bearer " + $credentials.apiKey : undefined }}',
      },
    },
  };

  test: ICredentialTestRequest = {
    request: {
      baseURL: '={{ $credentials.baseUrl }}',
      url: '/healthz',
      method: 'GET',
    },
  };
}
