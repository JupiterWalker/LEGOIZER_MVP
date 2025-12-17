import { LegoColor, ProcessingSettings } from './types';
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