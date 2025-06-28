#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import jsforce from 'jsforce';
import dotenv from 'dotenv';

dotenv.config();

class SalesforceMCPServer {
  private server: Server;
  private connection: jsforce.Connection | null = null;

  constructor() {
    this.server = new Server(
      {
        name: 'salesforce-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
  }

  private async connect(): Promise<void> {
    if (this.connection) return;

    const username = process.env.SALESFORCE_USERNAME;
    const password = process.env.SALESFORCE_PASSWORD;
    const token = process.env.SALESFORCE_SECURITY_TOKEN;
    const loginUrl = process.env.SALESFORCE_LOGIN_URL || 'https://login.salesforce.com';

    if (!username || !password || !token) {
      throw new Error('Missing Salesforce credentials in environment variables');
    }

    this.connection = new jsforce.Connection({
      loginUrl: loginUrl,
    });

    await this.connection.login(username, password + token);
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'query_salesforce',
            description: 'Execute SOQL query against Salesforce',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'SOQL query to execute',
                },
              },
              required: ['query'],
            },
          },
        ],
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      await this.connect();
      
      if (!this.connection) {
        throw new Error('Failed to establish Salesforce connection');
      }

      const { name, arguments: args } = request.params;

      switch (name) {
        case 'query_salesforce': {
          const result = await this.connection.query(args.query);
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(result, null, 2),
              },
            ],
          };
        }

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    });
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
  }
}

const server = new SalesforceMCPServer();
server.run().catch(console.error);