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
  Tabs, // Import Tabs
  rem, // Import rem for icon sizing
} from '@mantine/core';
import {
  IconUpload,
  IconFile,
  IconCheck,
  IconX,
  IconLoader,
  IconDatabase,
  IconBuildingBank, // Icon for Tab 1
  IconReportMoney, // Icon for Tab 2
} from '@tabler/icons-react';

// --- LOGGING TYPES (No change) ---
type LogType = 'info' | 'success' | 'error' | 'server';
interface LogMessage {
  type: LogType;
  text: string;
}
interface LogLineProps {
  type: LogType;
  text: string;
}

// --- NEW FILE UPLOAD COMPONENT ---
interface FileUploadAreaProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  isProcessing: boolean;
  title: string;
  description: string;
  themeColor: string;
}

// This is a reusable component for our upload zones
const FileUploadArea: React.FC<FileUploadAreaProps> = ({
  file,
  onFileChange,
  isProcessing,
  title,
  description,
  themeColor,
}) => {
  
  const handleMouseOver = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isProcessing) e.currentTarget.style.backgroundColor = 'var(--mantine-color-dark-5)';
  };
  
  const handleMouseOut = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isProcessing) e.currentTarget.style.backgroundColor = file ? `var(--mantine-color-${themeColor}-9)` : 'var(--mantine-color-dark-6)';
  };

  return (
    <FileButton onChange={onFileChange} accept=".pdf" disabled={isProcessing}>
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
          bg={file ? `${themeColor}.9` : 'dark.6'}
          onMouseOver={handleMouseOver}
          onMouseOut={handleMouseOut}
        >
          <ThemeIcon
            variant="light"
            color={file ? themeColor : 'indigo'}
            size="xl"
            radius="xl"
            mx="auto"
          >
            <IconUpload size={32} />
          </ThemeIcon>
          <Text mt="md" size="lg" fw={500}>
            {file ? (
              <Text span c={`${themeColor}.3`}>
                {file.name}
              </Text>
            ) : (
              <Text span c="indigo.3">
                {title}
              </Text>
            )}
          </Text>
          <Text size="sm" c="dimmed" mt={4}>
            {description}
          </Text>
        </Box>
      )}
    </FileButton>
  );
};

// --- LOG LINE COMPONENT (No change) ---
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

// --- MAIN DASHBOARD COMPONENT ---
export default function IngestionDashboard() {
  // We now have two separate file states
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [internalFile, setInternalFile] = useState<File | null>(null);
  
  // This state is SHARED between both tabs
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [logMessages, setLogMessages] = useState<LogMessage[]>([
    { type: 'info', text: 'Waiting for file...' },
  ]);

  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  // Helper for auto-scroll (No change)
  const scrollToBottom = () => {
    viewportRef.current?.scrollTo({ top: viewportRef.current.scrollHeight, behavior: 'smooth' });
  };
  
  // Helper to add logs (No change)
  const addLogs = (newLogs: LogMessage[]) => {
    setLogMessages(currentLogs => {
      const existingTexts = new Set(currentLogs.map(log => log.text));
      const filteredNewLogs = newLogs.filter(log => !existingTexts.has(log.text));
      if (filteredNewLogs.length > 0) {
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

  // Efeito de Polling (UPDATED)
  // This logic is shared. It polls /api/get_logs regardless of which job started it.
  useEffect(() => {
    if (currentJobId && isProcessing) {
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const response = await fetch(`/api/get_logs?job_id=${currentJobId}`);
          if (!response.ok) throw new Error(`Server error: ${response.statusText}`);
          
          const data = await response.json();
          if (data.logs && data.logs.length > 0) {
            const newLogs = data.logs as LogMessage[];
            addLogs(newLogs);

            const lastLog = newLogs[newLogs.length - 1];
            if ((lastLog.type === 'success' || lastLog.type === 'error') && lastLog.text.includes("Job")) {
              stopPolling();
              setIsProcessing(false);
              // Clear BOTH file inputs on completion
              setBankFile(null); 
              setInternalFile(null);
            }
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
          addLogs([{ type: 'error', text: `Failed to fetch logs: ${errorMessage}` }]);
          stopPolling();
          setIsProcessing(false);
        }
      }, 2000);
    }
    return () => stopPolling();
  }, [currentJobId, isProcessing]);

  // File change handlers for each tab
  const onBankFileChange = (selectedFile: File | null) => {
    if (selectedFile) {
      setBankFile(selectedFile);
      setLogMessages([{ type: 'info', text: `Bank file selected: ${selectedFile.name}` }]);
      setCurrentJobId(null);
    }
  };
  
  const onInternalFileChange = (selectedFile: File | null) => {
    if (selectedFile) {
      setInternalFile(selectedFile);
      setLogMessages([{ type: 'info', text: `Internal file selected: ${selectedFile.name}` }]);
      setCurrentJobId(null);
    }
  };

  // --- NEW GENERIC UPLOAD HANDLER ---
  const handleUpload = async (file: File | null, endpoint: string) => {
    if (!file) {
      addLogs([{ type: 'error', text: 'No file selected to upload.' }]);
      return;
    }

    setIsProcessing(true);
    setCurrentJobId(null);
    setLogMessages([]); // Clear logs for new job
    addLogs([{ type: 'info', text: `Uploading ${file.name} to ${endpoint}...` }]);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // 1. CHAMA O ENDPOINT CORRETO
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || 'Upload failed');

      // 2. SUCESSO! Define o job_id, o que dispara o useEffect de polling
      addLogs([{ type: 'success', text: 'Upload complete. Processing...' }]);
      setCurrentJobId(data.job_id);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      addLogs([{ type: 'error', text: `Upload failed: ${errorMessage}` }]);
      setIsProcessing(false);
      // Clear files on failure too
      setBankFile(null);
      setInternalFile(null);
    }
  };

  const iconStyle = { width: rem(16), height: rem(16) };

  return (
    <Box bg="dark.8" style={{ minHeight: '100vh' }}>
      <Container size="md" py="xl">
        <Paper withBorder shadow="xl" p="xl" radius="md" bg="dark.7">
          <header>
            <Title order={1} c="indigo.3">
              Financial Ingestion Dashboard
            </Title>
            <Text c="dimmed" mt="sm" mb="xl">
              Upload bank statements or internal reports for parsing and insertion.
            </Text>
          </header>

          {/* --- TABS --- */}
          <Tabs defaultValue="statements">
            <Tabs.List grow>
              <Tabs.Tab 
                value="statements" 
                leftSection={<IconBuildingBank style={iconStyle} />}
                disabled={isProcessing}
              >
                Bank Statements
              </Tabs.Tab>
              <Tabs.Tab 
                value="internal" 
                leftSection={<IconReportMoney style={iconStyle} />}
                disabled={isProcessing}
              >
                Internal Reports
              </Tabs.Tab>
            </Tabs.List>

            {/* --- TAB 1: BANK STATEMENTS --- */}
            <Tabs.Panel value="statements" pt="xl">
              <FileUploadArea
                file={bankFile}
                onFileChange={onBankFileChange}
                isProcessing={isProcessing}
                title="Click to choose bank statement"
                description="Upload PDF files from the bank (e.g., ComprovanteBB...)"
                themeColor="green"
              />
              <Button
                onClick={() => handleUpload(bankFile, '/api/ingest')}
                disabled={!bankFile || isProcessing}
                loading={isProcessing}
                fullWidth
                size="lg"
                mt="xl"
                loaderProps={{ children: <IconLoader /> }}
                color="green"
              >
                {isProcessing ? 'Processing...' : 'Upload Bank Statement'}
              </Button>
            </Tabs.Panel>

            {/* --- TAB 2: INTERNAL REPORTS --- */}
            <Tabs.Panel value="internal" pt="xl">
               <FileUploadArea
                file={internalFile}
                onFileChange={onInternalFileChange}
                isProcessing={isProcessing}
                title="Click to choose internal report"
                description="Upload 'pagamentos' or 'recebimentos' PDFs"
                themeColor="blue"
              />
              <Button
                onClick={() => handleUpload(internalFile, '/api/ingest_internal')}
                disabled={!internalFile || isProcessing}
                loading={isProcessing}
                fullWidth
                size="lg"
                mt="xl"
                loaderProps={{ children: <IconLoader /> }}
                color="blue"
              >
                {isProcessing ? 'Processing...' : 'Upload Internal Report'}
              </Button>
            </Tabs.Panel>
          </Tabs>

          {/* --- LIVE LOGGER (SHARED) --- */}
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