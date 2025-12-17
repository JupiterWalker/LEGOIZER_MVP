import * as THREE from 'three';
import { VoxelStruct, BrickType } from '../types';
import { BRICK_HEIGHT_RATIO, PLATE_HEIGHT_RATIO } from '../constants';

/**
 * Voxelizes a mesh using Ray Casting (Scanline) to generate a solid structure.
 * Scans the mesh grid column by column (X, Z) and fills intervals along Y.
 */
export const voxelizeMesh = (
  mesh: THREE.Mesh, 
  resolution: number, 
  hexColor: string,
  brickType: BrickType
): VoxelStruct[] => {
  // Ensure mesh world matrix is up to date for raycasting
  mesh.updateMatrixWorld(true);
  
  const geometry = mesh.geometry;
  geometry.computeBoundingBox();
  const box = geometry.boundingBox!;
  
  const size = new THREE.Vector3();
  box.getSize(size);
  
  // 1. Grid Dimensions
  // Align grid to the longest axis of the footprint (X or Z) to keep studs square
  const maxDim = Math.max(size.x, size.z);
  
  // Safety check
  if (maxDim <= 0.001) return [];

  const unitSize = maxDim / resolution;
  
  const xCount = Math.ceil(size.x / unitSize);
  const zCount = Math.ceil(size.z / unitSize);
  
  const heightRatio = brickType === 'plate' ? PLATE_HEIGHT_RATIO : BRICK_HEIGHT_RATIO;
  const unitHeight = unitSize * heightRatio;

  const voxels: VoxelStruct[] = [];
  let idCounter = 0;

  const raycaster = new THREE.Raycaster();
  const rayDir = new THREE.Vector3(0, 1, 0); // Up
  const rayOrigin = new THREE.Vector3();

  // 2. Scanline Raycasting
  // Iterate through every X, Z column in the grid
  for (let i = 0; i < xCount; i++) {
    for (let k = 0; k < zCount; k++) {
      // Ray Origin: Center of the voxel column
      const centerX = box.min.x + (i + 0.5) * unitSize;
      const centerZ = box.min.z + (k + 0.5) * unitSize;
      
      // Start ray slightly below the mesh bounding box
      rayOrigin.set(centerX, box.min.y - 0.5, centerZ);
      raycaster.set(rayOrigin, rayDir);
      
      // Intersect with the mesh
      const intersects = raycaster.intersectObject(mesh, false);
      
      // 3. Solid Fill Logic (Parity Rule)
      // Raycaster returns intersections sorted by distance.
      // We assume pairs of intersections represent entering and exiting the solid volume.
      // [Enter, Exit], [Enter, Exit] ...
      
      for (let m = 0; m < intersects.length; m += 2) {
         if (m + 1 >= intersects.length) break; // Need a complete pair
         
         const yEnter = intersects[m].point.y;
         const yExit = intersects[m+1].point.y;
         
         // Convert World Y range to Grid Y indices
         // We check which voxel centers fall within the [Enter, Exit] interval
         
         // Voxel center Y formula: box.min.y + (j + 0.5) * unitHeight
         // Solving for j:
         const jStart = Math.ceil((yEnter - box.min.y) / unitHeight - 0.5);
         const jEnd = Math.floor((yExit - box.min.y) / unitHeight - 0.5);
         
         for (let j = jStart; j <= jEnd; j++) {
           if (j >= 0) {
             voxels.push({
               id: idCounter++,
               x: i,
               y: j,
               z: k,
               c: hexColor
             });
           }
         }
      }
    }
  }

  return voxels;
};