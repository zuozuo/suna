import { extractToolData, extractCommand, extractCommandOutput, extractExitCode, extractSessionName } from '../utils';

export interface CommandData {
  command: string | null;
  output: string | null;
  exitCode: number | null;
  sessionName: string | null;
  cwd: string | null;
  completed: boolean | null;
  success?: boolean;
  timestamp?: string;
}

const parseContent = (content: any): any => {
  if (typeof content === 'string') {
    try {
      return JSON.parse(content);
    } catch (e) {
      return content;
    }
  }
  return content;
};


const extractFromNewFormat = (content: any): CommandData => {
  const parsedContent = parseContent(content);
  
  if (!parsedContent || typeof parsedContent !== 'object') {
    return { command: null, output: null, exitCode: null, sessionName: null, cwd: null, completed: null, success: undefined, timestamp: undefined };
  }

  if ('tool_execution' in parsedContent && typeof parsedContent.tool_execution === 'object') {
    const toolExecution = parsedContent.tool_execution;
    const args = toolExecution.arguments || {};
    
    let parsedOutput = toolExecution.result?.output;
    if (typeof parsedOutput === 'string') {
      try {
        parsedOutput = JSON.parse(parsedOutput);
      } catch (e) {
      }
    }
    parsedOutput = parsedOutput || {};

    const extractedData = {
      command: args.command || null,
      output: parsedOutput?.output || null,
      exitCode: parsedOutput?.exit_code || null,
      sessionName: args.session_name || parsedOutput?.session_name || null,
      cwd: parsedOutput?.cwd || null,
      completed: parsedOutput?.completed || null,
      success: toolExecution.result?.success,
      timestamp: toolExecution.execution_details?.timestamp
    };

    console.log('CommandToolView: Extracted from new format:', {
      command: extractedData.command,
      hasOutput: !!extractedData.output,
      exitCode: extractedData.exitCode,
      sessionName: extractedData.sessionName,
      success: extractedData.success
    });
    
    return extractedData;
  }

  if ('role' in parsedContent && 'content' in parsedContent) {
    return extractFromNewFormat(parsedContent.content);
  }

  return { command: null, output: null, exitCode: null, sessionName: null, cwd: null, completed: null, success: undefined, timestamp: undefined };
};


const extractFromLegacyFormat = (content: any): Omit<CommandData, 'success' | 'timestamp'> => {
  const toolData = extractToolData(content);
  
  if (toolData.toolResult) {
    const args = toolData.arguments || {};
    
    console.log('CommandToolView: Extracted from legacy format (extractToolData):', {
      command: toolData.command || args.command,
      hasOutput: !!toolData.toolResult.toolOutput
    });
    
    return {
      command: toolData.command || args.command || null,
      output: toolData.toolResult.toolOutput || null,
      exitCode: null,
      sessionName: args.session_name || null,
      cwd: null,
      completed: null
    };
  }

  const legacyCommand = extractCommand(content);
  
  console.log('CommandToolView: Extracted from legacy format (fallback):', {
    command: legacyCommand
  });
  
  return {
    command: legacyCommand,
    output: null,
    exitCode: null,
    sessionName: null,
    cwd: null,
    completed: null
  };
};

export function extractCommandData(
  assistantContent: any,
  toolContent: any,
  isSuccess: boolean,
  toolTimestamp?: string,
  assistantTimestamp?: string
): {
  command: string | null;
  output: string | null;
  exitCode: number | null;
  sessionName: string | null;
  cwd: string | null;
  completed: boolean | null;
  actualIsSuccess: boolean;
  actualToolTimestamp?: string;
  actualAssistantTimestamp?: string;
} {
  let command: string | null = null;
  let output: string | null = null;
  let exitCode: number | null = null;
  let sessionName: string | null = null;
  let cwd: string | null = null;
  let completed: boolean | null = null;
  let actualIsSuccess = isSuccess;
  let actualToolTimestamp = toolTimestamp;
  let actualAssistantTimestamp = assistantTimestamp;

  const assistantNewFormat = extractFromNewFormat(assistantContent);
  const toolNewFormat = extractFromNewFormat(toolContent);

  console.log('CommandToolView: Format detection results:', {
    assistantNewFormat: {
      hasCommand: !!assistantNewFormat.command,
      hasOutput: !!assistantNewFormat.output,
      sessionName: assistantNewFormat.sessionName
    },
    toolNewFormat: {
      hasCommand: !!toolNewFormat.command,
      hasOutput: !!toolNewFormat.output,
      sessionName: toolNewFormat.sessionName
    }
  });

  if (assistantNewFormat.command || assistantNewFormat.output) {
    command = assistantNewFormat.command;
    output = assistantNewFormat.output;
    exitCode = assistantNewFormat.exitCode;
    sessionName = assistantNewFormat.sessionName;
    cwd = assistantNewFormat.cwd;
    completed = assistantNewFormat.completed;
    if (assistantNewFormat.success !== undefined) {
      actualIsSuccess = assistantNewFormat.success;
    }
    if (assistantNewFormat.timestamp) {
      actualAssistantTimestamp = assistantNewFormat.timestamp;
    }
    console.log('CommandToolView: Using assistant new format data');
  } else if (toolNewFormat.command || toolNewFormat.output) {
    command = toolNewFormat.command;
    output = toolNewFormat.output;
    exitCode = toolNewFormat.exitCode;
    sessionName = toolNewFormat.sessionName;
    cwd = toolNewFormat.cwd;
    completed = toolNewFormat.completed;
    if (toolNewFormat.success !== undefined) {
      actualIsSuccess = toolNewFormat.success;
    }
    if (toolNewFormat.timestamp) {
      actualToolTimestamp = toolNewFormat.timestamp;
    }
    console.log('CommandToolView: Using tool new format data');
  } else {
    const assistantLegacy = extractFromLegacyFormat(assistantContent);
    const toolLegacy = extractFromLegacyFormat(toolContent);

    command = assistantLegacy.command || toolLegacy.command;
    output = assistantLegacy.output || toolLegacy.output;
    sessionName = assistantLegacy.sessionName || toolLegacy.sessionName;
    
    console.log('CommandToolView: Using legacy format data:', {
      command,
      hasOutput: !!output,
      sessionName
    });
  }

  if (!command) {
    const rawCommand = extractCommand(assistantContent) || extractCommand(toolContent);
    command = rawCommand
      ?.replace(/^suna@computer:~\$\s*/g, '')
      ?.replace(/\\n/g, '')
      ?.replace(/\n/g, '')
      ?.trim() || null;
  }
  
  if (!output && toolContent) {
    output = extractCommandOutput(toolContent);
  }
  
  if (exitCode === null && toolContent) {
    exitCode = extractExitCode(toolContent);
  }

  if (!sessionName) {
    sessionName = extractSessionName(assistantContent) || extractSessionName(toolContent);
  }

  if (output && typeof output === 'string' && output.includes('exit_code=') && exitCode === null) {
    const exitCodeMatch = output.match(/exit_code=(\d+)/);
    if (exitCodeMatch) {
      exitCode = parseInt(exitCodeMatch[1], 10);
    }
  }


  return {
    command,
    output,
    exitCode,
    sessionName,
    cwd,
    completed,
    actualIsSuccess,
    actualToolTimestamp,
    actualAssistantTimestamp
  };
} 