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
  Tabs,
  rem,
  SimpleGrid, // For DRE Stats
  Select,     // For Month/Year inputs
  Table,      // For DRE lists
  LoadingOverlay,
  Badge,
} from '@mantine/core';
import {
  IconUpload,
  IconFile,
  IconCheck,
  IconX,
  IconLoader,
  IconDatabase,
  IconBuildingBank,
  IconReportMoney,
  IconChartPie, // Icon for DRE Tab
  IconArrowUpRight,
  IconArrowDownRight,
  IconScale,
  IconAlertTriangle,
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

// --- NEW DRE DATA TYPES ---
interface DREData {
  dre: {
    total_receitas: number;
    total_despesas: number;
    net_profit: number;
  };
  reconciliation: {
    total_received_bank: number;
    total_paid_bank: number;
    discrepancy_receitas: number;
    discrepancy_despesas: number;
  };
  lists: {
    receitas: any[];
    despesas: any[];
  };
}

// --- FILE UPLOAD COMPONENT (No change) ---
interface FileUploadAreaProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  isProcessing: boolean;
  title: string;
  description: string;
  themeColor: string;
}

const FileUploadArea: React.FC<FileUploadAreaProps> = ({
  file, onFileChange, isProcessing, title, description, themeColor
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
        <Box {...props}
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
          <ThemeIcon variant="light" color={file ? themeColor : 'indigo'} size="xl" radius="xl" mx="auto">
            <IconUpload size={32} />
          </ThemeIcon>
          <Text mt="md" size="lg" fw={500}>
            {file ? (
              <Text span c={`${themeColor}.3`}>{file.name}</Text>
            ) : (
              <Text span c="indigo.3">{title}</Text>
            )}
          </Text>
          <Text size="sm" c="dimmed" mt={4}>{description}</Text>
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
      <Text c={colors[type]} size="sm" ff="monospace">{text}</Text>
    </Group>
  );
};

// --- NEW STATS CARD COMPONENT ---
interface StatCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  color?: string;
}
const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color = "gray" }) => {
  return (
    <Paper withBorder p="md" radius="md" bg="dark.6">
      <Group justify="space-between">
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          {title}
        </Text>
        <ThemeIcon color={color} variant="light" size={28} radius="md">
          {icon}
        </ThemeIcon>
      </Group>
      <Text size="xl" fw={700} c={color}>
        {value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
      </Text>
    </Paper>
  );
};

// --- MAIN DASHBOARD COMPONENT ---
export default function IngestionDashboard() {
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [internalFile, setInternalFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [logMessages, setLogMessages] = useState<LogMessage[]>([
    { type: 'info', text: 'Waiting for file...' },
  ]);

  // --- NEW DRE STATE ---
  const [reportYear, setReportYear] = useState<string | null>(new Date().getFullYear().toString());
  const [reportMonth, setReportMonth] = useState<string | null>((new Date().getMonth() + 1).toString());
  const [dreData, setDreData] = useState<DREData | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(false);

  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const theme = useMantineTheme();

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

  // Limpa o intervalo de polling (No change)
  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  // Efeito de Polling (No change)
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

  // File change handlers (No change)
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

  // Generic upload handler (No change)
  const handleUpload = async (file: File | null, endpoint: string) => {
    if (!file) {
      addLogs([{ type: 'error', text: 'No file selected to upload.' }]);
      return;
    }
    setIsProcessing(true);
    setCurrentJobId(null);
    setLogMessages([]);
    addLogs([{ type: 'info', text: `Uploading ${file.name} to ${endpoint}...` }]);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(endpoint, { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail?.message || data.detail || 'Upload failed');
      addLogs([{ type: 'success', text: 'Upload complete. Processing...' }]);
      setCurrentJobId(data.job_id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      addLogs([{ type: 'error', text: `Upload failed: ${errorMessage}` }]);
      setIsProcessing(false);
      setBankFile(null);
      setInternalFile(null);
    }
  };

  // --- NEW DRE REPORT HANDLER ---
  const handleGenerateReport = async () => {
    if (!reportYear || !reportMonth) {
      alert("Please select a year and month.");
      return;
    }
    setIsReportLoading(true);
    setDreData(null);
    try {
      const response = await fetch(`/api/reports/monthly_dre?year=${reportYear}&month=${reportMonth}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Failed to generate report');
      setDreData(data);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      alert(`Report Error: ${errorMessage}`);
    } finally {
      setIsReportLoading(false);
    }
  };

  const iconStyle = { width: rem(16), height: rem(16) };

  // --- RENDER ---
  return (
    <Box bg="dark.8" style={{ minHeight: '100vh' }}>
      <Container size="xl" py="xl"> 
        <Paper withBorder shadow="xl" p="xl" radius="md" bg="dark.7">
          <header>
            <Title order={1} c="indigo.3">Financial Ingestion & Reporting</Title>
            <Text c="dimmed" mt="sm" mb="xl">
              Upload statements or generate your monthly DRE.
            </Text>
          </header>

          <Tabs defaultValue="statements">
            <Tabs.List grow>
              <Tabs.Tab value="statements" leftSection={<IconBuildingBank style={iconStyle} />} disabled={isProcessing}>
                Bank Statements
              </Tabs.Tab>
              <Tabs.Tab value="internal" leftSection={<IconReportMoney style={iconStyle} />} disabled={isProcessing}>
                Internal Reports
              </Tabs.Tab>
              <Tabs.Tab value="dre" leftSection={<IconChartPie style={iconStyle} />} disabled={isProcessing}>
                Monthly DRE
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
              <Button onClick={() => handleUpload(bankFile, '/api/ingest')} disabled={!bankFile || isProcessing} loading={isProcessing} fullWidth size="lg" mt="xl" loaderProps={{ children: <IconLoader /> }} color="green">
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
              <Button onClick={() => handleUpload(internalFile, '/api/ingest_internal')} disabled={!internalFile || isProcessing} loading={isProcessing} fullWidth size="lg" mt="xl" loaderProps={{ children: <IconLoader /> }} color="blue">
                {isProcessing ? 'Processing...' : 'Upload Internal Report'}
              </Button>
            </Tabs.Panel>

            {/* --- TAB 3: MONTHLY DRE --- */}
            <Tabs.Panel value="dre" pt="xl">
              <Box pos="relative">
                <LoadingOverlay visible={isReportLoading} zIndex={10} overlayProps={{ radius: "sm", blur: 2 }} />
                <Group grow>
                  <Select
                    label="Month"
                    placeholder="Select month"
                    value={reportMonth}
                    onChange={setReportMonth}
                    data={[
                      { value: '1', label: 'January' }, { value: '2', label: 'February' },
                      { value: '3', label: 'March' }, { value: '4', label: 'April' },
                      { value: '5', label: 'May' }, { value: '6', label: 'June' },
                      { value: '7', label: 'July' }, { value: '8', label: 'August' },
                      { value: '9', label: 'September' }, { value: '10', label: 'October' },
                      { value: '11', label: 'November' }, { value: '12', label: 'December' },
                    ]}
                  />
                  <Select
                    label="Year"
                    placeholder="Select year"
                    value={reportYear}
                    onChange={setReportYear}
                    data={['2023', '2024', '2025', '2026']}
                  />
                </Group>
                <Button onClick={handleGenerateReport} fullWidth size="lg" mt="xl" loaderProps={{ children: <IconLoader /> }}>
                  Generate Report
                </Button>

                {dreData && (
                  <Box mt="xl">
                    <Title order={3} size="h4" c="gray.4" mb="md">
                      Report for {reportMonth}/{reportYear}
                    </Title>
                    {/* DRE Stats */}
                    <SimpleGrid cols={{ base: 1, sm: 3 }} mb="xl">
                      <StatCard title="Receita (Internal)" value={dreData.dre.total_receitas} icon={<IconArrowUpRight size={18} />} color={theme.colors.green[5]} />
                      <StatCard title="Despesas (Internal)" value={dreData.dre.total_despesas} icon={<IconArrowDownRight size={18} />} color={theme.colors.red[5]} />
                      <StatCard title="Lucro Líquido (Internal)" value={dreData.dre.net_profit} icon={<IconScale size={18} />} color={dreData.dre.net_profit > 0 ? theme.colors.green[5] : theme.colors.red[5]} />
                    </SimpleGrid>
                    {/* Reconciliation Stats */}
                    <Title order={4} size="h5" c="gray.4" mb="md">Reconciliation vs. Bank</Title>
                    <SimpleGrid cols={{ base: 1, sm: 2 }} mb="xl">
                       <StatCard title="Discrepância (Receitas)" value={dreData.reconciliation.discrepancy_receitas} icon={<IconAlertTriangle size={18} />} color={dreData.reconciliation.discrepancy_receitas !== 0 ? theme.colors.yellow[5] : theme.colors.gray[5]} />
                       <StatCard title="Discrepância (Despesas)" value={dreData.reconciliation.discrepancy_despesas} icon={<IconAlertTriangle size={18} />} color={dreData.reconciliation.discrepancy_despesas !== 0 ? theme.colors.yellow[5] : theme.colors.gray[5]} />
                    </SimpleGrid>
                    
                    {/* Detail Lists */}
                    <Tabs defaultValue="receitas" variant="outline">
                      <Tabs.List>
                        <Tabs.Tab value="receitas">Receitas Pagas ({dreData.lists.receitas.length})</Tabs.Tab>
                        <Tabs.Tab value="despesas">Despesas Pagas ({dreData.lists.despesas.length})</Tabs.Tab>
                      </Tabs.List>
                      <Tabs.Panel value="receitas" pt="xs">
                        <ScrollArea h={300}>
                          <Table striped highlightOnHover withTableBorder>
                            <Table.Thead>
                              <Table.Tr>
                                <Table.Th>Entidade</Table.Th>
                                <Table.Th>Valor Pago</Table.Th>
                                <Table.Th>Vencimento</Table.Th>
                              </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>{dreData.lists.receitas.map((item: any, idx: number) => (
                              <Table.Tr key={idx}>
                                <Table.Td>{item.entity_name}</Table.Td>
                                <Table.Td>{(item.paid_amount).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</Table.Td>
                                <Table.Td>{new Date(item.due_date).toLocaleDateString('pt-BR')}</Table.Td>
                              </Table.Tr>
                            ))}</Table.Tbody>
                          </Table>
                        </ScrollArea>
                      </Tabs.Panel>
                      <Tabs.Panel value="despesas" pt="xs">
                         <ScrollArea h={300}>
                          <Table striped highlightOnHover withTableBorder>
                            <Table.Thead>
                              <Table.Tr>
                                <Table.Th>Categoria</Table.Th>
                                <Table.Th>Entidade</Table.Th>
                                <Table.Th>Valor Pago</Table.Th>
                                <Table.Th>Vencimento</Table.Th>
                              </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>{dreData.lists.despesas.map((item: any, idx: number) => (
                              <Table.Tr key={idx}>
                                <Table.Td><Badge color="gray" variant="light">{item.category}</Badge></Table.Td>
                                <Table.Td>{item.entity_name}</Table.Td>
                                <Table.Td>{(item.paid_amount).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</Table.Td>
                                <Table.Td>{new Date(item.due_date).toLocaleDateString('pt-BR')}</Table.Td>
                              </Table.Tr>
                            ))}</Table.Tbody>
                          </Table>
                        </ScrollArea>
                      </Tabs.Panel>
                    </Tabs>
                  </Box>
                )}
              </Box>
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