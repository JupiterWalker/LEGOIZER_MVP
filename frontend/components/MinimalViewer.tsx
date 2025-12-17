import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

// A minimal Three.js viewer to verify WebGL support: renders a rotating cube
export default function MinimalViewer() {
  const mountRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const cubeRef = useRef<THREE.Mesh | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // Basic WebGL availability check
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) {
      setError('WebGL is not available. Please check your browser/GPU drivers.');
      return;
    }

    try {
      const width = mount.clientWidth;
      const height = mount.clientHeight;

      const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio);
      rendererRef.current = renderer;
      mount.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      scene.background = new THREE.Color('#1a1a1a');
      sceneRef.current = scene;

      const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
      camera.position.set(3, 3, 5);
      cameraRef.current = camera;

      const ambient = new THREE.AmbientLight(0xffffff, 0.6);
      scene.add(ambient);
      const dir = new THREE.DirectionalLight(0xffffff, 0.8);
      dir.position.set(5, 10, 7);
      scene.add(dir);

      const geometry = new THREE.BoxGeometry(1, 1, 1);
      const material = new THREE.MeshStandardMaterial({ color: 0x4ade80 }); // green
      const cube = new THREE.Mesh(geometry, material);
      cube.castShadow = true;
      cube.receiveShadow = true;
      scene.add(cube);
      cubeRef.current = cube;

      const animate = () => {
        if (!rendererRef.current || !sceneRef.current || !cameraRef.current || !cubeRef.current) return;
        requestAnimationFrame(animate);
        cubeRef.current.rotation.y += 0.01;
        cubeRef.current.rotation.x += 0.005;
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      };
      animate();

      const handleResize = () => {
        if (!mount || !rendererRef.current || !cameraRef.current) return;
        const w = mount.clientWidth;
        const h = mount.clientHeight;
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      };
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        if (rendererRef.current) {
          rendererRef.current.dispose();
          if (rendererRef.current.domElement && rendererRef.current.domElement.parentNode === mount) {
            mount.removeChild(rendererRef.current.domElement);
          }
        }
        if (cubeRef.current) {
          cubeRef.current.geometry.dispose();
          (cubeRef.current.material as THREE.Material).dispose();
        }
      };
    } catch (e) {
      console.error('Three.js initialization failed', e);
      setError('Three.js initialization failed.');
    }
  }, []);

  return (
    <div className="relative w-full h-full bg-neutral-900 overflow-hidden">
      <div ref={mountRef} className="w-full h-full" />
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
          <div className="text-center">
            <div className="text-red-400 font-bold mb-2">{error}</div>
            <div className="text-neutral-300 text-sm">Try enabling hardware acceleration or updating drivers.</div>
          </div>
        </div>
      )}
    </div>
  );
}
