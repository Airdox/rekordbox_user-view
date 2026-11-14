import express from 'express'
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createInterface } from 'node:readline'
import { createServer as createViteServer } from 'vite'

const PORT = 3000
const ALLOWED_METHODS = new Set([
  'open',
  'demoLibrary',
  'query',
  'detail',
  'interfaces',
  'usb',
  'linkStart',
  'linkStop',
  'demoLink',
  'live',
  'bindMedia',
  'unbindMedia',
  'rekordboxTransport',
])

const rootDir = process.cwd()
const fixturePath = join(rootDir, 'build', 'synthetic_test_master.db')
const statePath = join(rootDir, '.cuepoint-state.json')
const defaultMasterPath = 'E:\\PIONEER\\Master'

function savedWebPath(): string | undefined {
  try {
    const parsed = JSON.parse(readFileSync(statePath, 'utf8')) as { path?: unknown }
    return typeof parsed?.path === 'string' && parsed.path.length > 0 ? parsed.path : undefined
  } catch {
    return undefined
  }
}

function rememberWebPath(path: string): void {
  try {
    writeFileSync(statePath + '.tmp', JSON.stringify({ path }), 'utf8')
    renameSync(statePath + '.tmp', statePath)
  } catch {
    /* ignore write errors in read-only environments */
  }
}

interface PendingEntry {
  resolve: (value: unknown) => void
  reject: (reason: Error & { errorCode?: string }) => void
  timeout: ReturnType<typeof setTimeout>
}

class PythonBridge {
  private worker: ChildProcessWithoutNullStreams | undefined
  private workerError: string | undefined
  private nextId = 0
  private pending = new Map<number, PendingEntry>()
  private queue: Promise<void> = Promise.resolve()

  constructor() {
    this.launch()
  }

  private launch() {
    const executable =
      process.platform === 'win32'
        ? existsSync(join(rootDir, '.venv', 'Scripts', 'python.exe'))
          ? join(rootDir, '.venv', 'Scripts', 'python.exe')
          : 'py'
        : 'python3'
    const args = [
      ...(executable === 'py' ? ['-3.11'] : []),
      '-u',
      join(rootDir, 'backend', 'main.py'),
    ]

    this.workerError = undefined
    const child = spawn(executable, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: rootDir,
      env: { ...process.env, PYTHONUTF8: '1' },
    })
    this.worker = child

    const fail = (message: string) => {
      if (this.worker !== child) return
      this.worker = undefined
      this.workerError = message
      for (const entry of this.pending.values()) {
        clearTimeout(entry.timeout)
        const err = new Error(message) as Error & { errorCode?: string }
        err.errorCode = 'PYTHON_WORKER_UNAVAILABLE'
        entry.reject(err)
      }
      this.pending.clear()
    }

    child.on('error', (error) => fail(error.message))
    child.on('exit', (code) => fail(`Der Python-Dienst wurde beendet (${code}).`))
    child.stdin.on('error', (error) => fail(error.message))
    child.stderr.on('data', (chunk) => process.stderr.write(chunk))
    createInterface({ input: child.stdout }).on('line', (line) => {
      let data: { id?: number; result?: unknown; error?: string; errorCode?: string }
      try {
        data = JSON.parse(line)
      } catch {
        return
      }
      if (typeof data.id !== 'number') return
      const entry = this.pending.get(data.id)
      if (!entry) return
      clearTimeout(entry.timeout)
      this.pending.delete(data.id)
      if (data.error) {
        const err = new Error(data.error) as Error & { errorCode?: string }
        if (data.errorCode) err.errorCode = data.errorCode
        entry.reject(err)
      } else {
        entry.resolve(data.result)
      }
    })
  }

  request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    if (!ALLOWED_METHODS.has(method)) {
      return Promise.reject(new Error('Unbekannter Bibliotheksbefehl.'))
    }
    const run = async () => {
      if (!this.worker) {
        this.launch()
      }
      const active = this.worker
      if (!active) {
        const err = new Error(this.workerError || 'Der Python-Dienst ist nicht verfügbar.') as Error & {
          errorCode?: string
        }
        err.errorCode = 'PYTHON_WORKER_UNAVAILABLE'
        throw err
      }
      let effectiveMethod = method
      let resolvedParams = params
      if (method === 'open') {
        const explicitPath = typeof params.path === 'string' && params.path.trim() ? params.path.trim() : undefined
        const previousPath = process.env.CUEPOINT_LIBRARY_PATH || savedWebPath()
        const candidatePath = explicitPath || (previousPath && existsSync(previousPath) ? previousPath : undefined)
        if (candidatePath) {
          resolvedParams = { ...params, path: candidatePath }
        } else if (!explicitPath && !existsSync(defaultMasterPath)) {
          effectiveMethod = 'demoLibrary'
          resolvedParams = existsSync(fixturePath) ? { path: fixturePath } : {}
        }
      } else if (method === 'demoLibrary' && !params.path && existsSync(fixturePath)) {
        resolvedParams = { path: fixturePath }
      }
      const res = await new Promise<unknown>((resolve, reject) => {
        const id = ++this.nextId
        const timeout = setTimeout(() => {
          this.pending.delete(id)
          const err = new Error('Zeitüberschreitung beim Lesen der Bibliothek.') as Error & {
            errorCode?: string
          }
          err.errorCode = 'IPC_TIMEOUT'
          reject(err)
        }, 90_000)
        this.pending.set(id, { resolve, reject, timeout })
        active.stdin.write(JSON.stringify({ id, method: effectiveMethod, params: resolvedParams }) + '\n')
      })
      if (
        effectiveMethod === 'open' &&
        !process.env.CUEPOINT_LIBRARY_PATH &&
        res &&
        typeof res === 'object' &&
        typeof (res as { path?: unknown }).path === 'string'
      ) {
        rememberWebPath((res as { path: string }).path)
      }
      return res
    }

    const result = this.queue.then(run, run)
    this.queue = result.then(
      () => undefined,
      () => undefined,
    )
    return result
  }

  close() {
    this.worker?.stdin.end()
  }
}

async function startServer() {
  mkdirSync(join(rootDir, 'build'), { recursive: true })
  const generatorScript = join(rootDir, 'tests', 'generate_synthetic_db.py')
  if (!existsSync(fixturePath) && existsSync(generatorScript)) {
    const pythonExe =
      process.platform === 'win32'
        ? existsSync(join(rootDir, '.venv', 'Scripts', 'python.exe'))
          ? join(rootDir, '.venv', 'Scripts', 'python.exe')
          : 'py'
        : 'python3'
    spawnSync(pythonExe, [...(pythonExe === 'py' ? ['-3.11'] : []), generatorScript], {
      cwd: rootDir,
      stdio: 'ignore',
    })
  }
  const bridge = new PythonBridge()
  const app = express()
  app.use(express.json({ limit: '2mb' }))

  app.get('/api/cuepoint/health', (_req, res) => {
    res.json({
      ok: true,
      mode: 'web-bridge',
      platform: process.platform,
      hasSyntheticFixture: existsSync(fixturePath),
    })
  })

  app.get('/api/cuepoint/sources', async (_req, res) => {
    try {
      const usb = (await bridge.request('usb', {})) as string[]
      res.json({
        usb,
        sampleFixture: existsSync(fixturePath) ? fixturePath : null,
      })
    } catch (error) {
      const err = error as Error & { errorCode?: string }
      res.status(500).json({ error: err.message, errorCode: err.errorCode ?? 'SOURCE_UNREADABLE' })
    }
  })

  app.post('/api/cuepoint/open-sample', async (_req, res) => {
    try {
      const result = await bridge.request('demoLibrary', existsSync(fixturePath) ? { path: fixturePath } : {})
      res.json({ result })
    } catch (error) {
      const err = error as Error & { errorCode?: string }
      res.status(400).json({ error: err.message, errorCode: err.errorCode ?? 'SOURCE_UNREADABLE' })
    }
  })

  app.post('/api/cuepoint/request', async (req, res) => {
    const method = typeof req.body?.method === 'string' ? req.body.method : ''
    const params =
      req.body?.params && typeof req.body.params === 'object' ? (req.body.params as Record<string, unknown>) : {}
    if (!ALLOWED_METHODS.has(method)) {
      res.status(400).json({ error: 'Unbekannter Bibliotheksbefehl.', errorCode: 'SOURCE_UNREADABLE' })
      return
    }
    try {
      const result = await bridge.request(method, params)
      res.json({ result })
    } catch (error) {
      const err = error as Error & { errorCode?: string }
      res.status(200).json({ error: err.message, errorCode: err.errorCode })
    }
  })

  const distDir = join(rootDir, 'dist')
  const useStatic = process.env.NODE_ENV === 'production' && existsSync(join(distDir, 'index.html'))
  if (useStatic) {
    app.use(express.static(distDir))
    app.get('*', (_req, res) => {
      res.sendFile(resolve(distDir, 'index.html'))
    })
  } else {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        allowedHosts: true,
        hmr: process.env.DISABLE_HMR !== 'true',
      },
      appType: 'spa',
    })
    app.use(vite.middlewares)
  }

  const server = app.listen(PORT, '0.0.0.0', () => {
    console.log(`Cuepoint bridge listening on http://localhost:${PORT}`)
  })

  const shutdown = () => {
    bridge.close()
    server.close(() => process.exit(0))
  }
  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)
}

startServer().catch((err) => {
  console.error('Failed to start Cuepoint server:', err)
  process.exit(1)
})
