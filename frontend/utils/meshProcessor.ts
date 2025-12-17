import * as THREE from 'three';
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

const TARGET_SIZE = 40; // Normalize loaded models to this size for consistent viewing/voxelization

export const processMesh = (mesh: THREE.Mesh): THREE.Mesh => {
  let geometry = mesh.geometry;

  // 1. Coordinate System Adjustment: 
  // Trusting source coordinates as per user request (no rotation).

  // 2. Ensure non-indexed geometry for easier face filtering
  if (geometry.index) {
    geometry = geometry.toNonIndexed();
  }

  // 3. Clean NaN/Inf values and Remove Degenerate Faces
  const posAttribute = geometry.attributes.position;
  const positions = posAttribute.array;
  const normals = geometry.attributes.normal?.array;
  const uvs = geometry.attributes.uv?.array;

  const newPos: number[] = [];
  const newNorm: number[] = [];
  const newUv: number[] = [];

  const _p1 = new THREE.Vector3();
  const _p2 = new THREE.Vector3();
  const _p3 = new THREE.Vector3();
  const _edge1 = new THREE.Vector3();
  const _edge2 = new THREE.Vector3();
  const _cross = new THREE.Vector3();

  for (let i = 0; i < positions.length; i += 9) {
    let valid = true;

    // Check NaNs/Infs
    for (let j = 0; j < 9; j++) {
      if (!Number.isFinite(positions[i + j])) {
        valid = false;
        break;
      }
    }

    if (valid) {
      // Check Area (Remove degenerate faces)
      _p1.set(positions[i], positions[i + 1], positions[i + 2]);
      _p2.set(positions[i + 3], positions[i + 4], positions[i + 5]);
      _p3.set(positions[i + 6], positions[i + 7], positions[i + 8]);

      _edge1.subVectors(_p2, _p1);
      _edge2.subVectors(_p3, _p1);
      _cross.crossVectors(_edge1, _edge2);
      
      // Tolerance for zero area
      if (_cross.lengthSq() < 1e-12) {
        valid = false;
      }
    }

    if (valid) {
      for (let j = 0; j < 9; j++) newPos.push(positions[i + j]);
      if (normals) for (let j = 0; j < 9; j++) newNorm.push(normals[i + j]);
      if (uvs) {
        // UVs are 2D, so 6 floats per face (3 verts * 2 coords)
        const uvStart = (i / 3) * 2;
        for (let j = 0; j < 6; j++) newUv.push(uvs[uvStart + j]);
      }
    }
  }

  const cleanedGeometry = new THREE.BufferGeometry();
  cleanedGeometry.setAttribute('position', new THREE.Float32BufferAttribute(newPos, 3));
  if (newNorm.length > 0) cleanedGeometry.setAttribute('normal', new THREE.Float32BufferAttribute(newNorm, 3));
  if (newUv.length > 0) cleanedGeometry.setAttribute('uv', new THREE.Float32BufferAttribute(newUv, 2));

  // 4. Merge Vertices (Equivalent to removing duplicates and repairing)
  geometry = mergeVertices(cleanedGeometry);

  // 5. Recompute Normals
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();

  // 6. Normalize Scale (Auto-Scale)
  // Ensure the model isn't too small or too huge by scaling it to TARGET_SIZE
  console.log('[processMesh] vertex count:', newPos.length / 3);
  if (geometry.boundingBox) {
    const size = new THREE.Vector3();
    geometry.boundingBox.getSize(size);
    console.log('[processMesh] bbox size:', size);
    const maxDim = Math.max(size.x, size.y, size.z);
    
    if (maxDim > 0) {
        const scaleFactor = TARGET_SIZE / maxDim;
        geometry.scale(scaleFactor, scaleFactor, scaleFactor);
    }
    // Recompute bounding box after scale
    geometry.computeBoundingBox();
  }

  // 7. Center X/Z and Align Bottom Y to 0 (Floor)
  if (geometry.boundingBox) {
      const min = geometry.boundingBox.min;
      const center = new THREE.Vector3();
      geometry.boundingBox.getCenter(center);
      
      // Move center to (0, ?, 0) and bottom to 0
      geometry.translate(-center.x, -min.y, -center.z);
  }
  
  geometry.computeBoundingBox();
  mesh.geometry = geometry;
  return mesh;
};