export interface MCPConfiguration {
  name: string;
  qualifiedName: string;
  config: Record<string, any>;
  enabledTools?: string[];
  selectedProfileId?: string;
  isCustom?: boolean;
  customType?: 'http' | 'sse';
}
  
export interface MCPConfigurationProps {
  configuredMCPs: MCPConfiguration[];
  onConfigurationChange: (mcps: MCPConfiguration[]) => void;
}
