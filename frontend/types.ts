import { Vector3 } from 'three';

export interface VoxelStruct {
  id: number;
  x: number;
  y: number;
  z: number;
  c: string; // Hex color string
}

export interface VoxelData {
  position: Vector3;
  colorIndex: number;
}

export interface LegoColor {
  code: number;
  name: string;
  hex: string;
}

export type BrickType = 'brick' | 'plate';

export interface ProcessingSettings {
  resolution: number; // Grid size on the longest axis
  colorCode: number;
  brickType: BrickType;
  threshold: number;
}

export interface AiAnalysis {
  title: string;
  description: string;
  theme: string;
  piecesCount: number;
}

export interface MpdBrick {
  x: number; // LDraw units
  y: number; // LDraw units
  z: number; // LDraw units
  colorCode: number; // LDraw color code
  colorHex?: string; // Resolved hex when direct colour is present
}