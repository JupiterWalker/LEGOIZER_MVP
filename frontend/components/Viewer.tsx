import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VoxelStruct, BrickType, MpdBrick } from '../types';
import { LDRAW_UNIT_WIDTH, LDRAW_BRICK_HEIGHT, LDRAW_PLATE_HEIGHT, LEGO_COLORS, LEGO_COLOR_MAP, resolvePartDefinition } from '../constants';
import { processMesh, normalizeScene } from '../utils/meshProcessor';

interface ViewerProps {
  objFile: File | null;
  voxels: VoxelStruct[];
  mpdBricks?: MpdBrick[];
  gridSize: number;
  showOriginal: boolean;
  showGenerated: boolean;
  brickType: BrickType;
  lightRotation: number;
  onMeshLoaded: (mesh: THREE.Object3D) => void;
  isLoading: boolean;
}

export interface ViewerRef {
  getScreenshot: () => string;
}

const Viewer = forwardRef<ViewerRef, ViewerProps>(({ objFile, voxels, mpdBricks, gridSize, showOriginal, showGenerated, brickType, lightRotation, onMeshLoaded, isLoading }, ref) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const meshRef = useRef<THREE.Object3D | null>(null);
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

    // 防止在开发模式 / 热重载下重复挂载，先清空已有 canvas
    while (mountRef.current.firstChild) {
      mountRef.current.removeChild(mountRef.current.firstChild);
    }

    const width = mountRef.current.clientWidth;
    const height = mountRef.current.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#1a1a1a');
    // Add grid helper
    const gridHelper = new THREE.GridHelper(500, 50, 0x444444, 0x222222);
    scene.add(gridHelper);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000);
    camera.position.set(60, 60, 60);

    // Disable preserveDrawingBuffer/shadows to avoid driver bugs like glTexStorage2D immutable errors
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: false });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true; // Enable shadows for better visualization
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6); // Slightly brighter ambient
    scene.add(ambientLight);

    // Main Directional Light
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(50, 100, 50);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    scene.add(dirLight);
    lightRef.current = dirLight;

    // Back/Rim Light for better definition
    const backLight = new THREE.DirectionalLight(0xaaccff, 0.5);
    backLight.position.set(-50, 20, -50);
    backLight.castShadow = false;
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

  // Handle Model Loading (OBJ & GLB/GLTF)
  useEffect(() => {
    console.log('[Viewer] File changed:', objFile);
    if (!objFile || !sceneRef.current) return;

    const fileName = objFile.name.toLowerCase();
    const isGlb = fileName.endsWith('.glb') || fileName.endsWith('.gltf');

    // Cleanup previous
    if (meshRef.current) {
        sceneRef.current.remove(meshRef.current);
        meshRef.current = null;
    }

    if (isGlb) {
        const loader = new GLTFLoader();
        const reader = new FileReader();
        reader.onload = (e) => {
            const arrayBuffer = e.target?.result as ArrayBuffer;
            if (!arrayBuffer) return;
            
            loader.parse(arrayBuffer, '', (gltf) => {
                const object = gltf.scene;
                // console.log('[Viewer] GLB Loaded:', object);

                // Normalize scene (Scale & Center) without merging
                normalizeScene(object);

                // Add to scene
                meshRef.current = object;
                sceneRef.current?.add(object);

                // Update Camera
                cameraRef.current?.position.set(60, 60, 60);
                cameraRef.current?.lookAt(0, 0, 0);

                onMeshLoaded(object);
            }, (err) => {
                console.error('[Viewer] Error parsing GLB:', err);
            });
        };
        reader.readAsArrayBuffer(objFile);

    } else {
        // Assume OBJ
        const loader = new OBJLoader();
        const reader = new FileReader();

        reader.onload = (e) => {
            const result = e.target?.result as string;
            if (!result) return;
            const object = loader.parse(result);
            
            let mainMesh: THREE.Mesh | null = null;
            // Find the first mesh for processing (legacy logic for OBJ voxelization)
            object.traverse((child) => {
                if (!mainMesh && (child as THREE.Mesh).isMesh) {
                    mainMesh = child as THREE.Mesh;
                }
            });

            if (mainMesh) {
                // Process the mesh: Clean, Fix, Center, Auto-scale
                const processedMesh = processMesh(mainMesh as THREE.Mesh);

                // Apply wireframe material for OBJ visualization (as requested in original features)
                processedMesh.material = new THREE.MeshStandardMaterial({ 
                    color: 0xff0000, 
                    wireframe: true,
                    transparent: true,
                    opacity: 0.3,
                    side: THREE.FrontSide
                });

                const group = new THREE.Group();
                group.add(processedMesh);
                meshRef.current = group;
                sceneRef.current?.add(group);
                
                cameraRef.current?.position.set(60, 60, 60);
                cameraRef.current?.lookAt(0, 0, 0);
                console.log('[Viewer] OBJ processed and loaded');
                onMeshLoaded(processedMesh);
            }
        };
        reader.readAsText(objFile);
    }

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
  }, [brickType, gridSize]); 

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
    const TARGET_SIZE = 40;
    const gap = 0.98;
    const identityRotation = [1, 0, 0, 0, 1, 0, 0, 0, 1];
    const localCorners = [
      new THREE.Vector3(-0.5, -0.5, -0.5),
      new THREE.Vector3(0.5, -0.5, -0.5),
      new THREE.Vector3(-0.5, 0.5, -0.5),
      new THREE.Vector3(0.5, 0.5, -0.5),
      new THREE.Vector3(-0.5, -0.5, 0.5),
      new THREE.Vector3(0.5, -0.5, 0.5),
      new THREE.Vector3(-0.5, 0.5, 0.5),
      new THREE.Vector3(0.5, 0.5, 0.5),
    ];
    const transformed = new THREE.Vector3();
    const rotationMatrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();

    const resolveBrickHex = (brick: MpdBrick): string => {
      if (brick.colorHex) return brick.colorHex;
      const key = String(brick.colorCode);
      const direct = LEGO_COLOR_MAP[key];
      if (direct) return direct;
      return LEGO_COLORS.find(c => c.code === brick.colorCode)?.hex || '#ffffff';
    };

    // Group bricks by resolved colour string so instancing can reuse materials.
    const colourBuckets = new Map<string, MpdBrick[]>();
    for (const brick of mpdBricks) {
      const hex = resolveBrickHex(brick);
      if (!colourBuckets.has(hex)) {
        colourBuckets.set(hex, []);
      }
      colourBuckets.get(hex)!.push(brick);
    }

    // Track bounds for camera framing
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;

    colourBuckets.forEach((list, hex) => {
      const material = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.4, metalness: 0.1 });
      const geometry = new THREE.BoxGeometry(1, 1, 1);
      const instanced = new THREE.InstancedMesh(geometry, material, list.length);
      const dummy = new THREE.Object3D();
      const rotationArray = identityRotation;
      list.forEach((b, i) => {
        const definition = resolvePartDefinition(b.part);
        const studsX = definition?.studsX ?? 1;
        const studsY = definition?.studsY ?? 1;
        const family = definition?.family ?? brickType;
        const unitWidth = studsX * LDRAW_UNIT_WIDTH;
        const unitDepth = studsY * LDRAW_UNIT_WIDTH;
        const baseHeight = family === 'plate' ? LDRAW_PLATE_HEIGHT : LDRAW_BRICK_HEIGHT;
        const width = unitWidth * gap;
        const depth = unitDepth * gap;
        const height = baseHeight * gap;

        const rotationValues = b.rotation && b.rotation.length === 9 ? b.rotation : rotationArray;
        rotationMatrix.set(
          rotationValues[0], rotationValues[1], rotationValues[2], 0,
          rotationValues[3], rotationValues[4], rotationValues[5], 0,
          rotationValues[6], rotationValues[7], rotationValues[8], 0,
          0, 0, 0, 1
        );
        quaternion.setFromRotationMatrix(rotationMatrix);

        dummy.position.set(
          b.x,
          -b.y - height / 2,
          b.z
        );
        dummy.quaternion.copy(quaternion);
        dummy.scale.set(width, height, depth);
        dummy.updateMatrix();
        instanced.setMatrixAt(i, dummy.matrix);

        for (const corner of localCorners) {
          transformed.copy(corner).applyMatrix4(dummy.matrix);
          if (transformed.x < minX) minX = transformed.x;
          if (transformed.x > maxX) maxX = transformed.x;
          if (transformed.y < minY) minY = transformed.y;
          if (transformed.y > maxY) maxY = transformed.y;
          if (transformed.z < minZ) minZ = transformed.z;
          if (transformed.z > maxZ) maxZ = transformed.z;
        }
      });
      instanced.castShadow = true;
      instanced.receiveShadow = true;
      instanced.instanceMatrix.needsUpdate = true;
      group.add(instanced);
    });

    // Normalize MPD group
    const sizeX = maxX - minX;
    const sizeY = maxY - minY;
    const sizeZ = maxZ - minZ;
    const mpdMaxDim = Math.max(sizeX, sizeY, sizeZ);
    if (mpdMaxDim > 0) {
      const scaleFactor = TARGET_SIZE / mpdMaxDim;
      group.scale.set(scaleFactor, scaleFactor, scaleFactor);

      const centerX = ((minX + maxX) / 2) * scaleFactor;
      const centerZ = ((minZ + maxZ) / 2) * scaleFactor;
      const bottomY = minY * scaleFactor;
      group.position.set(-centerX, -bottomY, -centerZ);
    }

    group.visible = showGenerated;
    mpdGroupRef.current = group;
    sceneRef.current.add(group);

    if (cameraRef.current) {
      const maxDim = mpdMaxDim > 0 ? TARGET_SIZE : 100;
      const scaledCenterY = mpdMaxDim > 0 ? (sizeY * TARGET_SIZE) / (2 * mpdMaxDim) : (maxY - minY) / 2;
      const center = new THREE.Vector3(0, scaledCenterY, 0);
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

  useEffect(() => {
    if (mpdGroupRef.current) {
      mpdGroupRef.current.visible = showGenerated;
    }
  }, [showGenerated]);

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