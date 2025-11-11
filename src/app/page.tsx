// src/app/page.tsx
"use client";

import { useState, useEffect, useRef } from 'react';
import {
  Container,
  Paper,
  Title,
  Text,
  FileButton,
  Button,
  Group,
  ScrollArea,
  Box,
  ThemeIcon,
  useMantineTheme,
} from '@mantine/core';
import {
  IconUpload,
  IconFile,
  IconCheck,
  IconX,
  IconLoader,
  IconDatabase,
} from '@tabler/icons-react';

// Define o tipo para nossas mensagens de log
type LogType = 'info' | 'success' | 'error' | 'server';

interface LogMessage {
  type: LogType;
  text: string;
}

// Define os props para o componente LogLine
interface LogLineProps {
  type: LogType;
  text: string;
}

// Este é o componente principal do nosso dashboard, agora em TSX.
export default function IngestionDashboard() {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [logMessages, setLogMessages] = useState<LogMessage[]>([
    { type: 'info', text: 'Waiting for file...' },
  ]);

  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null); // Para o auto-scroll

  // Helper para auto-scroll do log
  const scrollToBottom = () => {
    viewportRef.current?.scrollTo({ top: viewportRef.current.scrollHeight, behavior: 'smooth' });
  };
  
  // Helper para adicionar logs e garantir que não haja duplicatas
  const addLogs = (newLogs: LogMessage[]) => {
    setLogMessages(currentLogs => {
      const existingTexts = new Set(currentLogs.map(log => log.text));
      // Filtra logs que já não existem no estado
      const filteredNewLogs = newLogs.filter(log => !existingTexts.has(log.text));
      if (filteredNewLogs.length > 0) {
        // Atraso de 10ms para dar tempo ao React de renderizar antes do scroll
        setTimeout(scrollToBottom, 10); 
        return [...currentLogs, ...filteredNewLogs];
      }
      return currentLogs;
    });
  };

  // Limpa o intervalo de polling
  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  // Efeito que inicia/para o polling baseado no currentJobId
  useEffect(() => {
    if (currentJobId && isProcessing) {
      // Inicia o polling
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const response = await fetch(`/api/get_logs?job_id=${currentJobId}`);
          if (!response.ok) {
            throw new Error(`Server error: ${response.statusText}`);
          }
          const data = await response.json();
          
          if (data.logs && data.logs.length > 0) {
            const newLogs = data.logs as LogMessage[];
            addLogs(newLogs);

            // Verifica se o job terminou
            const lastLog = newLogs[newLogs.length - 1];
            if ((lastLog.type === 'success' || lastLog.type === 'error') && lastLog.text.includes("Job")) {
              stopPolling();
              setIsProcessing(false);
              setFile(null); // Limpa o arquivo após o sucesso
            }
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
          addLogs([{ type: 'error', text: `Failed to fetch logs: ${errorMessage}` }]);
          stopPolling();
          setIsProcessing(false);
        }
      }, 2000); // Polling a cada 2 segundos
    }

    // Função de limpeza do useEffect
    return () => {
      stopPolling();
    };
  }, [currentJobId, isProcessing]); // Depende do job_id e do status

  // Lida com a seleção de arquivos
  const onFileChange = (selectedFile: File | null) => {
    if (selectedFile) {
      setFile(selectedFile);
      setLogMessages([{ type: 'info', text: `File selected: ${selectedFile.name}` }]);
      setCurrentJobId(null);
    }
  };

  // --- LÓGICA DE UPLOAD REAL ---
  const handleUpload = async () => {
    if (!file) {
      addLogs([{ type: 'error', text: 'No file selected to upload.' }]);
      return;
    }

    setIsProcessing(true);
    setCurrentJobId(null);
    setLogMessages([]); // Limpa os logs para um novo job
    addLogs([{ type: 'info', text: `Uploading ${file.name}...` }]);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // 1. CHAMA O /api/ingest
      const response = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Upload failed');
      }

      // 2. SUCESSO! Define o job_id, o que dispara o useEffect de polling
      addLogs([{ type: 'success', text: 'Upload complete. Processing...' }]);
      setCurrentJobId(data.job_id);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      addLogs([{ type: 'error', text: `Upload failed: ${errorMessage}` }]);
      setIsProcessing(false);
    }
  };

  // Componente UI para a linha de log
  const LogLine: React.FC<LogLineProps> = ({ type, text }) => {
    const theme = useMantineTheme();
    const icons: Record<LogType, React.ReactNode> = {
      info: <IconFile size={16} />,
      success: <IconCheck size={16} />,
      error: <IconX size={16} />,
      server: <IconDatabase size={16} />,
    };

    const colors: Record<LogType, string> = {
      info: theme.colors.blue[4],
      success: theme.colors.green[4],
      error: theme.colors.red[4],
      server: theme.colors.indigo[3],
    };

    return (
      <Group gap="xs">
        <ThemeIcon color={colors[type]} variant="light" size="sm">
          {icons[type] || <IconFile size={16} />}
        </ThemeIcon>
        <Text c={colors[type]} size="sm" ff="monospace">
          {text}
        </Text>
      </Group>
    );
  };

  // Tipa os eventos do mouse
  const handleMouseOver = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isProcessing) e.currentTarget.style.backgroundColor = 'var(--mantine-color-dark-5)';
  };
  
  const handleMouseOut = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isProcessing) e.currentTarget.style.backgroundColor = file ? 'var(--mantine-color-green-9)' : 'var(--mantine-color-dark-6)';
  };

  return (
    <Box bg="dark.8" style={{ minHeight: '100vh' }}>
      <Container size="md" py="xl">
        <Paper withBorder shadow="xl" p="xl" radius="md" bg="dark.7">
          <header>
            <Title order={1} c="indigo.3">
              Financial Ingestion Dashboard
            </Title>
            <Text c="dimmed" mt="sm" mb="xl">
              Upload new bank statements (PDF) for parsing and insertion into
              PostgreSQL.
            </Text>
          </header>

          {/* Upload Area */}
          <FileButton onChange={onFileChange} accept=".pdf,.zip" disabled={isProcessing}>
            {(props) => (
              <Box
                {...props}
                style={{
                  border: '2px dashed var(--mantine-color-gray-7)',
                  padding: '2rem',
                  borderRadius: 'var(--mantine-radius-md)',
                  textAlign: 'center',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  transition: 'background-color 0.2s',
                  opacity: isProcessing ? 0.5 : 1,
                }}
                bg={file ? 'green.9' : 'dark.6'}
                onMouseOver={handleMouseOver}
                onMouseOut={handleMouseOut}
              >
                <ThemeIcon
                  variant="light"
                  color={file ? 'green' : 'indigo'}
                  size="xl"
                  radius="xl"
                  mx="auto"
                >
                  <IconUpload size={32} />
                </ThemeIcon>
                <Text mt="md" size="lg" fw={500}>
                  {file ? (
                    <Text span c="green.3">
                      {file.name}
                    </Text>
                  ) : (
                    <Text span c="indigo.3">
                      Click to choose a file
                    </Text>
                  )}
                </Text>
                <Text size="sm" c="dimmed" mt={4}>
                  Drag & drop files here too. PDF or ZIP.
                </Text>
              </Box>
            )}
          </FileButton>

          <Button
            onClick={handleUpload}
            disabled={!file || isProcessing}
            loading={isProcessing}
            fullWidth
            size="lg"
            mt="xl"
            loaderProps={{ children: <IconLoader /> }}
          >
            {isProcessing ? 'Processing in Progress...' : 'Upload and Process File'}
          </Button>

          {/* Live Logger */}
          <Box mt="xl">
            <Title order={3} size="h4" c="gray.4" mb="md">
              Live Ingestion Log
            </Title>
            <ScrollArea h={300} bg="dark.9" p="md" viewportRef={viewportRef}>
              <Box style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {logMessages.map((msg, idx) => (
                  <LogLine key={idx} type={msg.type} text={msg.text} />
                ))}
              </Box>
            </ScrollArea>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}