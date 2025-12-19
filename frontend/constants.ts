import { LegoColor, PartDefinition, ProcessingSettings, BrickType } from './types';
import * as THREE from 'three';

// A subset of common LDraw/Lego colors
export const LEGO_COLORS: LegoColor[] = [
  { code: 4, name: "Red", hex: "#C91A09" },
  { code: 0, name: "Black", hex: "#05131D" },
  { code: 15, name: "White", hex: "#FFFFFF" },
  { code: 2, name: "Green", hex: "#237841" },
  { code: 1, name: "Blue", hex: "#0055BF" },
  { code: 14, name: "Yellow", hex: "#F2CD37" },
  { code: 71, name: "Light Bluish Gray", hex: "#A0A5A9" },
  { code: 72, name: "Dark Bluish Gray", hex: "#6C6E68" },
  { code: 19, name: "Tan", hex: "#E4CD9E" },
  { code: 28, name: "Dark Tan", hex: "#958A73" },
  { code: 25, name: "Orange", hex: "#FE8A18" },
  { code: 5, name: "Dark Red", hex: "#720E0F" },
];

export const DEFAULT_SETTINGS: ProcessingSettings = {
  resolution: 100,
  colorCode: 15, // White
  brickType: 'plate',
  threshold: 0.5
};

export const LDRAW_UNIT_WIDTH = 20;
export const LDRAW_UNIT_DEPTH = 20;

// Brick Dimensions
export const LDRAW_BRICK_HEIGHT = 24;
export const BRICK_HEIGHT_RATIO = LDRAW_BRICK_HEIGHT / LDRAW_UNIT_WIDTH; // 1.2

// Plate Dimensions (1/3 of a brick)
export const LDRAW_PLATE_HEIGHT = 8;
export const PLATE_HEIGHT_RATIO = LDRAW_PLATE_HEIGHT / LDRAW_UNIT_WIDTH; // 0.4

// Helper to find closest Lego color from a generic Hex
export const getNearestLegoColor = (hex: string): number => {
  const target = new THREE.Color(hex);
  let minDistance = Infinity;
  let closestCode = 0;

  for (const legoColor of LEGO_COLORS) {
    const current = new THREE.Color(legoColor.hex);
    // Euclidean distance in RGB space
    const distance = Math.sqrt(
      Math.pow(target.r - current.r, 2) +
      Math.pow(target.g - current.g, 2) +
      Math.pow(target.b - current.b, 2)
    );

    if (distance < minDistance) {
      minDistance = distance;
      closestCode = legoColor.code;
    }
  }
  return closestCode;
};

const PART_DEFINITIONS: Array<[string, BrickType, number, number]> = [
  ['3024', 'plate', 1, 1],
  ['3023', 'plate', 2, 1],
  ['3623', 'plate', 3, 1],
  ['3710', 'plate', 4, 1],
  ['3022', 'plate', 2, 2],
  ['3021', 'plate', 3, 2],
  ['3020', 'plate', 4, 2],
  ['3031', 'plate', 4, 4],
  ['3005', 'brick', 1, 1],
  ['3004', 'brick', 2, 1],
  ['3622', 'brick', 3, 1],
  ['3010', 'brick', 4, 1],
  ['3003', 'brick', 2, 2],
  ['3001', 'brick', 4, 2],
];

const createPartDefinition = (partId: string, family: BrickType, studsX: number, studsY: number): PartDefinition => ({
  part: `${partId}.dat`,
  family,
  studsX,
  studsY,
});

const buildPartLibrary = (): Record<string, PartDefinition> => {
  const entries: Record<string, PartDefinition> = {};
  for (const [partId, family, studsX, studsY] of PART_DEFINITIONS) {
    const definition = createPartDefinition(partId, family, studsX, studsY);
    const lowerId = partId.toLowerCase();
    const lowerFile = `${lowerId}.dat`;
    entries[lowerId] = definition;
    entries[lowerFile] = definition;
  }
  return entries;
};

export const PART_LIBRARY: Record<string, PartDefinition> = buildPartLibrary();

const FALLBACK_PART: PartDefinition = {
  part: '3024.dat',
  family: 'brick',
  studsX: 1,
  studsY: 1,
};

const normalizePartKey = (part: string): string => {
  const lower = part.trim().toLowerCase().replace(/\\/g, '/');
  const basename = lower.includes('/') ? lower.substring(lower.lastIndexOf('/') + 1) : lower;
  return basename;
};

export const resolvePartDefinition = (part: string | undefined | null): PartDefinition => {
  if (!part) {
    return FALLBACK_PART;
  }
  const base = normalizePartKey(part);
  const withoutExt = base.endsWith('.dat') ? base.slice(0, -4) : base;
  return PART_LIBRARY[base] ?? PART_LIBRARY[withoutExt] ?? FALLBACK_PART;
};

export const LEGO_COLOR_MAP: Record<string, string> = {
  '0': '#1b2a34',
  '1': '#1e5aa8',
  '2': '#00852b',
  '3': '#069d9f',
  '4': '#b40000',
  '5': '#d3359d',
  '6': '#543324',
  '7': '#8a928d',
  '8': '#545955',
  '9': '#97cbd9',
  '10': '#58ab41',
  '11': '#00aaa4',
  '12': '#f06d61',
  '13': '#f6a9bb',
  '14': '#fac80a',
  '15': '#f4f4f4',
  '17': '#add9a8',
  '18': '#ffd67f',
  '19': '#d7ba8c',
  '20': '#afbed6',
  '22': '#671f81',
  '23': '#0e3e9a',
  '25': '#d67923',
  '26': '#901f76',
  '27': '#a5ca18',
  '28': '#897d62',
  '29': '#ff9ecd',
  '30': '#a06eb9',
  '31': '#cda4de',
  '68': '#fdc383',
  '69': '#8a12a8',
  '70': '#5f3109',
  '71': '#969696',
  '72': '#646464',
  '73': '#7396c8',
  '74': '#7fc475',
  '77': '#fecccf',
  '78': '#ffc995',
  '84': '#aa7d55',
  '85': '#441a91',
  '86': '#7b5d41',
  '89': '#1c58a7',
  '92': '#bb805a',
  '100': '#f9b7a5',
  '110': '#26469a',
  '112': '#4861ac',
  '115': '#b7d425',
  '118': '#9cd6cc',
  '120': '#deea92',
  '123': '#ee5434',
  '125': '#f9a777',
  '128': '#ad6140',
  '151': '#c8c8c8',
  '191': '#fcac00',
  '212': '#9dc3f7',
  '213': '#476fb6',
  '216': '#872b17',
  '218': '#8e5597',
  '219': '#564e9d',
  '220': '#9195ca',
  '226': '#ffec6c',
  '232': '#77c9d8',
  '272': '#19325a',
  '288': '#00451a',
  '295': '#ff94c2',
  '308': '#352100',
  '313': '#abd9ff',
  '320': '#720012',
  '321': '#469bc3',
  '322': '#68c3e2',
  '323': '#d3f2ea',
  '326': '#e2f99a',
  '330': '#77774e',
  '335': '#88605e',
  '351': '#f785b1',
  '353': '#ff6d77',
  '366': '#d86d2c',
  '368': '#edff21',
  '370': '#755945',
  '373': '#75657d',
  '378': '#708e7c',
  '379': '#70819a'
};