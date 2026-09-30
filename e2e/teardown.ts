import { execSync } from 'node:child_process'

/** Stopping the webServer process does not always stop the container itself. */
export default function teardown() {
  execSync('docker rm -f home-hub-e2e >/dev/null 2>&1 || true')
}
