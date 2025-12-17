import { VoxelStruct, BrickType } from '../types';
import { LDRAW_UNIT_WIDTH, LDRAW_BRICK_HEIGHT, LDRAW_PLATE_HEIGHT, LDRAW_UNIT_DEPTH, getNearestLegoColor } from '../constants';

export const generateLDR = (voxels: VoxelStruct[], brickType: BrickType, filename: string = "model"): string => {
  const lines: string[] = [];
  
  // Header
  lines.push(`0 ${filename}`);
  lines.push(`0 Name: ${filename}`);
  lines.push(`0 Author: Brickify 3D`);
  lines.push(`0 !LICENSE Redistributable under CCAL version 2.0 : see CAreadme.txt`);
  lines.push(``);

  const partId = brickType === 'plate' ? '3024.dat' : '3005.dat';
  const unitHeight = brickType === 'plate' ? LDRAW_PLATE_HEIGHT : LDRAW_BRICK_HEIGHT;

  voxels.forEach(voxel => {
    // 1. Convert JSON Grid Coordinate to LDraw Coordinate
    // LDraw units are approx 20 per stud.
    const x = voxel.x * LDRAW_UNIT_WIDTH;
    const y = -(voxel.y * unitHeight); // Invert Y for LDraw standard (Y is down)
    const z = voxel.z * LDRAW_UNIT_DEPTH;
    
    // 2. Resolve Color
    const ldrawColorCode = getNearestLegoColor(voxel.c);

    // 3. Generate Line
    // Format: 1 <colour> x y z a b c d e f g h i <file>
    lines.push(`1 ${ldrawColorCode} ${x} ${y} ${z} 1 0 0 0 1 0 0 0 1 ${partId}`);
  });

  return lines.join('\n');
};

export const downloadFile = (content: string, filename: string) => {
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};