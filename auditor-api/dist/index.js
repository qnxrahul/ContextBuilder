import Fastify from 'fastify';
import multipart from '@fastify/multipart';
import cors from '@fastify/cors';
import { v4 as uuidv4 } from 'uuid';
import fastifySSE from 'fastify-sse-v2';
const server = Fastify({ logger: true });
await server.register(cors, { origin: true });
await server.register(multipart);
await server.register(fastifySSE);
const sessionState = new Map();
server.get('/health', async () => ({ ok: true }));
server.post('/session', async (req, reply) => {
    const sessionId = uuidv4();
    const state = { sessionId, status: 'idle' };
    sessionState.set(sessionId, state);
    return reply.send({ sessionId });
});
server.get('/session/:id', async (req, reply) => {
    const { id } = req.params;
    const state = sessionState.get(id);
    if (!state)
        return reply.code(404).send({ error: 'not_found' });
    return reply.send(state);
});
server.get('/session/:id/stream', async (req, reply) => {
    const { id } = req.params;
    const state = sessionState.get(id);
    if (!state)
        return reply.code(404).send({ error: 'not_found' });
    reply.sse({ data: JSON.stringify({ type: 'snapshot', state }) });
    // In a real implementation, you would keep the connection and emit deltas.
    // Here we end after initial snapshot to keep example simple.
    reply.raw.end();
});
server.post('/upload/:id', async (req, reply) => {
    const { id } = req.params;
    const state = sessionState.get(id);
    if (!state)
        return reply.code(404).send({ error: 'not_found' });
    const parts = req.parts();
    for await (const part of parts) {
        if (part.type === 'file') {
            // Consume stream to buffer (simple demo; consider storage in production)
            const chunks = [];
            for await (const chunk of part.file)
                chunks.push(chunk);
            const fileBuffer = Buffer.concat(chunks);
            const fileName = part.filename || 'document';
            state.status = 'processing';
            // Simple placeholder analysis pipeline
            const text = fileBuffer.toString('utf8');
            const updated = {
                ...state,
                status: 'completed',
                summary: {
                    purpose: inferPurpose(text),
                    reportingPeriod: inferReportingPeriod(text),
                    highlights: inferHighlights(text)
                },
                metrics: computeDummyMetrics(text),
                compliance: detectDummyCompliance(text),
                trends: computeDummyTrends(text),
                anomalies: detectDummyAnomalies(text),
                structure: inferDummyStructure(text, fileName),
                highlights: inferDummyAuditHighlights(text),
                references: extractDummyReferences(text),
                suggestions: suggestDummyInsights(text),
            };
            sessionState.set(id, updated);
            return reply.send({ ok: true });
        }
    }
    return reply.code(400).send({ error: 'no_file' });
});
server.post('/analyze/:id', async (req, reply) => {
    const { id } = req.params;
    const state = sessionState.get(id);
    if (!state)
        return reply.code(404).send({ error: 'not_found' });
    // In a full implementation, trigger agents. Here, echo current state.
    return reply.send({ state });
});
function inferPurpose(text) {
    if (/financial statements?/i.test(text))
        return 'Financial Statement';
    if (/audit report/i.test(text))
        return 'Audit Report';
    if (/tax/i.test(text))
        return 'Tax Filing';
    return 'General Financial Document';
}
function inferReportingPeriod(text) {
    const m = text.match(/(FY|Fiscal Year)\s*(\d{4})/i) || text.match(/(Q[1-4])\s*(\d{4})/i);
    return m ? m[0] : undefined;
}
function inferHighlights(text) {
    return { notes: text.length > 100 ? 'Large document' : 'Small document' };
}
function computeDummyMetrics(_text) {
    return {
        profitability: { grossMargin: 0.42, netMargin: 0.12, roe: 0.15 },
        liquidity: { currentRatio: 1.8, quickRatio: 1.2 },
        solvency: { debtToEquity: 0.6, interestCoverage: 4.1 },
        efficiency: { inventoryTurnover: 5.2, receivablesTurnover: 7.8 }
    };
}
function detectDummyCompliance(_text) {
    return { missingData: false, unusualTransactions: false, lateFilings: false, standard: 'GAAP' };
}
function computeDummyTrends(_text) {
    return { revenue: [10, 12, 15, 14], expenses: [6, 7, 8, 9], assets: [20, 22, 25, 27], liabilities: [8, 9, 9, 10] };
}
function detectDummyAnomalies(_text) {
    return { spikes: [], duplicates: [], relatedParty: [], unusualEntries: [] };
}
function inferDummyStructure(_text, fileName) {
    return { toc: ['Executive Summary', 'Financial Metrics', 'Compliance'], figures: [], glossary: [], entities: [], fileName };
}
function inferDummyAuditHighlights(_text) {
    return { judgmentAreas: [], estimates: [], controls: [], auditorsOpinion: undefined };
}
function extractDummyReferences(_text) {
    return [];
}
function suggestDummyInsights(_text) {
    return { questions: ['What drove margin changes?'], deepDive: ['Receivables aging'], risks: ['Interest rate risk'], opportunities: ['Working capital optimization'] };
}
const port = process.env.PORT ? Number(process.env.PORT) : 8080;
server
    .listen({ port, host: '0.0.0.0' })
    .then(() => {
    server.log.info(`API running on http://0.0.0.0:${port}`);
})
    .catch((err) => {
    server.log.error(err);
    process.exit(1);
});
