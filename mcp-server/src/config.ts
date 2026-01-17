/**Configuration for MCP server.*/

export interface Config {
  /**Backend API base URL.*/
  backendUrl: string;
}

/**
 * Get configuration from environment variables.
 */
export function getConfig(): Config {
  return {
    backendUrl:
      process.env.OBSIDIAN_MEMORY_BACKEND_URL ||
      'http://localhost:8000',
  };
}
