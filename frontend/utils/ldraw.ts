import { MpdBrick } from '../types';

// Minimal parser for LDraw/MPD: extracts type-1 lines (subfile references)
// Format: 1 <color> x y z a b c d e f g h i <file>
// We only use color and position (x y z). All numbers are in LDraw units.
export function parseMpdInstances(text: string): MpdBrick[] {
  const lines = text.split(/\r?\n/);
  const bricks: MpdBrick[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('0 ')) continue; // comment/meta
    if (line[0] !== '1') continue; // only type-1 refs

    // Split keeping numeric tokens; file name may contain spaces but usually doesn't
    // We'll parse first 14 tokens strictly: [1, color, x, y, z, a..i] then remainder is file
    const parts = line.split(/\s+/);
    if (parts.length < 14) continue;

    const colorToken = parts[1];
    let colorCode = Number.NaN;
    let colorHex: string | undefined;
    if (/^0x/i.test(colorToken)) {
      colorCode = Number.parseInt(colorToken, 16);
      if (Number.isFinite(colorCode)) {
        const rgb = colorCode & 0xFFFFFF;
        colorHex = `#${rgb.toString(16).padStart(6, '0')}`;
      }
    } else {
      colorCode = Number.parseInt(colorToken, 10);
    }
    const x = parseFloat(parts[2]);
    const y = parseFloat(parts[3]);
    const z = parseFloat(parts[4]);

    const rotationTokens = parts.slice(5, 14).map((token) => parseFloat(token));
    const rotation = rotationTokens.length === 9 && rotationTokens.every((value) => Number.isFinite(value))
      ? rotationTokens
      : [1, 0, 0, 0, 1, 0, 0, 0, 1];

    const partTokens = parts.slice(14);
    const part = partTokens.join(' ');

    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) && Number.isFinite(colorCode)) {
      bricks.push({ x, y, z, colorCode, colorHex, part, rotation });
    }
  }
  return bricks;
}
