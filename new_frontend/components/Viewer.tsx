import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';
import { VoxelStruct, BrickType, MpdBrick } from '../types';
import { BRICK_HEIGHT_RATIO, PLATE_HEIGHT_RATIO, LDRAW_UNIT_WIDTH, LDRAW_BRICK_HEIGHT, LDRAW_PLATE_HEIGHT, LEGO_COLORS } from '../constants';
import { processMesh } from '../utils/meshProcessor';

interface ViewerProps {
  objFile: File | null;
  voxels: VoxelStruct[];
  mpdBricks?: MpdBrick[];
  gridSize: number;
  showOriginal: boolean;
  brickType: BrickType;
  lightRotation: number;
  onMeshLoaded: (mesh: THREE.Mesh) => void;
  isLoading: boolean;
}

export interface ViewerRef {
  getScreenshot: () => string;
}

const Viewer = forwardRef<ViewerRef, ViewerProps>(({ objFile, voxels, mpdBricks, gridSize, showOriginal, brickType, lightRotation, onMeshLoaded, isLoading }, ref) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const meshRef = useRef<THREE.Group | null>(null);
  const voxelGroupRef = useRef<THREE.Group | null>(null);
  const mpdGroupRef = useRef<THREE.Group | null>(null);
  const lightRef = useRef<THREE.DirectionalLight | null>(null);

  useImperativeHandle(ref, () => ({
    getScreenshot: () => {
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
        return rendererRef.current.domElement.toDataURL('image/png');
      }
      return '';
    }
  }));

  // Initialize Three.js
  useEffect(() => {
    if (!mountRef.current) return;

    const width = mountRef.current.clientWidth;
    const height = mountRef.current.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#1a1a1a');
    // Add grid helper
    const gridHelper = new THREE.GridHelper(500, 50, 0x444444, 0x222222);
    scene.add(gridHelper);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000);
    camera.position.set(60, 60, 60);

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap; // Softer shadows
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
    scene.add(ambientLight);
    scene.add(hemiLight);

    // Main Directional Light
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(50, 100, 50);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.bias = -0.0001;
    scene.add(dirLight);
    lightRef.current = dirLight;

    // Back/Rim Light for better definition
    const backLight = new THREE.DirectionalLight(0xaaccff, 0.5);
    backLight.position.set(-50, 20, -50);
    scene.add(backLight);

    sceneRef.current = scene;
    rendererRef.current = renderer;
    cameraRef.current = camera;

    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
        if(mountRef.current && cameraRef.current && rendererRef.current) {
            cameraRef.current.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
            cameraRef.current.updateProjectionMatrix();
            rendererRef.current.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
        }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Update Light Rotation
  useEffect(() => {
    if (lightRef.current) {
        const rad = (lightRotation * Math.PI) / 180;
        const radius = 100;
        // Orbit the light around Y axis
        lightRef.current.position.set(
            Math.sin(rad) * radius,
            80, 
            Math.cos(rad) * radius
        );
        lightRef.current.updateMatrixWorld();
    }
  }, [lightRotation]);

  // Handle OBJ Loading
  useEffect(() => {
    console.log('[Viewer] OBJ File changed:', objFile);
    if (!objFile || !sceneRef.current) return;

    const loader = new OBJLoader();
    const reader = new FileReader();

    reader.onload = (e) => {
      const result = e.target?.result as string;
      console.log('OBJ file content:', result); // 调试日志
      if (!result) return;
      const object = loader.parse(result);
      console.log('Parsed OBJ object:', object); // 调试日志
      
      // Cleanup previous
      if (meshRef.current) sceneRef.current.remove(meshRef.current);

      // Process new object
      const group = new THREE.Group();
      let mainMesh: THREE.Mesh | null = null;

      // Find the first mesh
      object.traverse((child) => {
        console.log('Traversing child:', child); // 调试日志
        if (!mainMesh && (child as THREE.Mesh).isMesh) {
          mainMesh = child as THREE.Mesh;
        }
      });

      if (mainMesh) {
        console.log('[Viewer] Loaded main mesh:', mainMesh);
          // Process the mesh: Clean, Fix, Center, Auto-scale
          const processedMesh = processMesh(mainMesh as THREE.Mesh);

          // Apply material
          processedMesh.material = new THREE.MeshStandardMaterial({ 
             color: 0x00ff00, 
             wireframe: true,
             transparent: true,
             opacity: 0.3,
             side: THREE.DoubleSide
          });

          group.add(processedMesh); 
          meshRef.current = group;
          sceneRef.current.add(group);
          
          // Fit camera to the new geometry size
          const box = processedMesh.geometry.boundingBox!;
          const size = new THREE.Vector3();
          box.getSize(size);
          const maxDim = Math.max(size.x, size.y, size.z);
          cameraRef.current?.position.set(maxDim * 1.5, maxDim * 1.5, maxDim * 1.5);
          cameraRef.current?.lookAt(0, size.y / 2, 0);
          console.log('[Viewer] Camera repositioned for new mesh: ', processedMesh);
          onMeshLoaded(processedMesh);
      }
    };

    reader.readAsText(objFile);
  }, [objFile]);

  // Handle Voxel Rendering from JSON structure
  useEffect(() => {
    if (!sceneRef.current) return;

    // Cleanup previous voxels
    if (voxelGroupRef.current) {
        sceneRef.current.remove(voxelGroupRef.current);
        voxelGroupRef.current.children.forEach((c) => {
           const mesh = c as THREE.Mesh;
           mesh.geometry.dispose();
           (mesh.material as THREE.Material).dispose();
        });
        voxelGroupRef.current = null;
    }

    if (voxels.length === 0) return;

    const group = new THREE.Group();
    // Scale the entire group to match the original mesh dimensions
    // Since voxels are normalized integers, multiplying by gridSize restores the world scale
    group.scale.set(gridSize, gridSize, gridSize);
    
    // Geometry Definition
    const heightRatio = brickType === 'plate' ? PLATE_HEIGHT_RATIO : BRICK_HEIGHT_RATIO;
    const gapScale = 0.95;
    const geometry = new THREE.BoxGeometry(
        1 * gapScale, 
        heightRatio * gapScale, 
        1 * gapScale
    );
    
    // Group voxels by Color Hex for instancing efficiency
    const colorGroups = new Map<string, VoxelStruct[]>();
    voxels.forEach(v => {
        if(!colorGroups.has(v.c)) colorGroups.set(v.c, []);
        colorGroups.get(v.c)?.push(v);
    });

    colorGroups.forEach((voxelList, hexColor) => {
        const material = new THREE.MeshStandardMaterial({ 
            color: hexColor,
            roughness: 0.4,
            metalness: 0.1
        });
        
        const instancedMesh = new THREE.InstancedMesh(geometry, material, voxelList.length);
        const dummy = new THREE.Object3D();

        voxelList.forEach((v, i) => {
             // Position mapping from JSON integer coordinates
             dummy.position.set(
                v.x, 
                v.y * heightRatio + (heightRatio / 2), 
                v.z
             );
             dummy.updateMatrix();
             instancedMesh.setMatrixAt(i, dummy.matrix);
        });
        
        instancedMesh.castShadow = true;
        instancedMesh.receiveShadow = true;
        group.add(instancedMesh);
    });

    voxelGroupRef.current = group;
    sceneRef.current.add(group);

  }, [voxels, brickType, gridSize]); 

  // Handle MPD brick rendering (if provided)
  useEffect(() => {
    if (!sceneRef.current) return;

    // Cleanup previous MPD group
    if (mpdGroupRef.current) {
      sceneRef.current.remove(mpdGroupRef.current);
      mpdGroupRef.current.children.forEach((c) => {
        const mesh = c as THREE.Mesh;
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      });
      mpdGroupRef.current = null;
    }

    if (!mpdBricks || mpdBricks.length === 0) return;

    const group = new THREE.Group();

    const height = brickType === 'plate' ? LDRAW_PLATE_HEIGHT : LDRAW_BRICK_HEIGHT;
    const gap = 0.98;
    const geom = new THREE.BoxGeometry(
      LDRAW_UNIT_WIDTH * gap,
      height * gap,
      LDRAW_UNIT_WIDTH * gap
    );

    // Map color code to hex
    const codeToHex = (code: number) => LEGO_COLORS.find(c => c.code === code)?.hex || '#FFFFFF';

    // Group by color
    const colorMap = new Map<number, MpdBrick[]>();
    for (const b of mpdBricks) {
      if (!colorMap.has(b.colorCode)) colorMap.set(b.colorCode, []);
      colorMap.get(b.colorCode)!.push(b);
    }

    // Track bounds for camera framing
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

    colorMap.forEach((list, code) => {
      const material = new THREE.MeshStandardMaterial({ color: codeToHex(code), roughness: 0.4, metalness: 0.1 });
      const instanced = new THREE.InstancedMesh(geom, material, list.length);
      const dummy = new THREE.Object3D();
      list.forEach((b, i) => {
        // Center cube at brick center; add half height on Y to stand on ground if positions are bottom-centered
        dummy.position.set(b.x, b.y + height / 2, b.z);
        dummy.updateMatrix();
        instanced.setMatrixAt(i, dummy.matrix);

        // Update bounds (use center +/- half extents)
        const halfX = (LDRAW_UNIT_WIDTH * gap) / 2;
        const halfY = (height * gap) / 2;
        const halfZ = (LDRAW_UNIT_WIDTH * gap) / 2;
        minX = Math.min(minX, b.x - halfX); maxX = Math.max(maxX, b.x + halfX);
        minY = Math.min(minY, b.y);       maxY = Math.max(maxY, b.y + height);
        minZ = Math.min(minZ, b.z - halfZ); maxZ = Math.max(maxZ, b.z + halfZ);
      });
      instanced.castShadow = true;
      instanced.receiveShadow = true;
      group.add(instanced);
    });

    mpdGroupRef.current = group;
    sceneRef.current.add(group);

    // Frame camera to fit MPD
    if (cameraRef.current) {
      const sizeX = maxX - minX;
      const sizeY = maxY - minY;
      const sizeZ = maxZ - minZ;
      const maxDim = Math.max(sizeX, sizeY, sizeZ);
      const center = new THREE.Vector3((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);
      cameraRef.current.position.set(center.x + maxDim * 1.5, center.y + maxDim * 1.5, center.z + maxDim * 1.5);
      cameraRef.current.lookAt(center);
    }
  }, [mpdBricks, brickType]);

  // Toggle Original Mesh visibility
  useEffect(() => {
     if(meshRef.current) {
       meshRef.current.visible = showOriginal;
     }
  }, [showOriginal]);

  return (
    <div className="relative w-full h-full bg-neutral-900 overflow-hidden">
        <div ref={mountRef} className="w-full h-full" />
        {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
                <div className="flex flex-col items-center">
                    <div className="w-10 h-10 border-4 border-yellow-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                    <div className="text-white font-bold text-xl animate-pulse">Processing...</div>
                    <div className="text-neutral-400 text-sm mt-2">Computing 3D Geometry</div>
                </div>
            </div>
        )}
    </div>
  );
});

export default Viewer;