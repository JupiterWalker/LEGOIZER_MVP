import React, { useState, useRef, useEffect } from 'react';
import * as THREE from 'three';
import { Upload, Download, Settings, RefreshCw, Box, Eye, EyeOff, Sparkles, Layers, Sun, FileJson } from 'lucide-react';
import MinimalViewer from './components/MinimalViewer';
import { generateLDR, downloadFile } from './utils/exporter';
import { voxelizeMesh } from './utils/voxelizer';
import { analyzeModel } from './services/aiService';
import { LEGO_COLORS, DEFAULT_SETTINGS } from './constants';
import { ProcessingSettings, VoxelStruct, AiAnalysis, MpdBrick } from './types';
import { parseMpdInstances } from './utils/ldraw';
import Viewer, { ViewerRef } from './components/Viewer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const parseFilenameFromContentDisposition = (header: string | null): string | null => {
    if (!header) return null;
    const match = header.match(/filename\*?=([^;]+)/i);
    if (!match) return null;
    const value = match[1].trim().replace(/^"|"$/g, '');
    try {
        return decodeURIComponent(value.replace(/UTF-8''/, ''));
    } catch (error) {
        return value;
    }
};

export default function App() {
  const viewerRef = useRef<ViewerRef>(null);
  const [file, setFile] = useState<File | null>(null);
  const [mesh, setMesh] = useState<THREE.Mesh | null>(null);
  const [voxels, setVoxels] = useState<VoxelStruct[]>([]);
    const [mpdBricks, setMpdBricks] = useState<MpdBrick[] | null>(null);
  const [gridSize, setGridSize] = useState<number>(1);
  const [settings, setSettings] = useState<ProcessingSettings>({
      ...DEFAULT_SETTINGS
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [showOriginal, setShowOriginal] = useState(true);
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [lightRotation, setLightRotation] = useState(45); // Degrees
  const [resolution, setResolution] = useState(100); // Longest side size in mm
    const [mpdDownloadUrl, setMpdDownloadUrl] = useState<string | null>(null);
    const [mpdFilename, setMpdFilename] = useState<string | null>(null);
    const [reportMetadata, setReportMetadata] = useState<Record<string, unknown> | null>(null);
    const [apiError, setApiError] = useState<string | null>(null);

    useEffect(() => {
        return () => {
            if (mpdDownloadUrl) {
                URL.revokeObjectURL(mpdDownloadUrl);
            }
        };
    }, [mpdDownloadUrl]);

    const brickCount = typeof reportMetadata?.count === 'number' ? (reportMetadata.count as number) : null;
    const voxelCount = typeof reportMetadata?.voxels === 'number' ? (reportMetadata.voxels as number) : null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setIsDone(false);
    console.log(e.target.files);
    if (e.target.files && e.target.files[0]) {
        console.log('Selected file:', e.target.files[0]);
      setFile(e.target.files[0]);
      setVoxels([]);
            setMpdBricks(null);
      setGridSize(1);
      setMesh(null);
      setAiAnalysis(null);
      setShowOriginal(true);
    }
  };

  const handleVoxelizeGeometric = async () => {
        if (!mesh || !file) return;
        setIsProcessing(true);
        setApiError(null);
        setReportMetadata(null);
        setMpdFilename(null);
        setMpdDownloadUrl(null);
        setMpdBricks(null);
        setIsDone(false);

        // try {
        //     const selectedColor = LEGO_COLORS.find(c => c.code === settings.colorCode) || LEGO_COLORS[0];
        //     const newVoxels = voxelizeMesh(
        //         mesh,
        //         settings.resolution,
        //         selectedColor.hex,
        //         settings.brickType
        //     );

        //     const meshSize = 40;
        //     const newGridSize = meshSize / settings.resolution;

        //     setVoxels(newVoxels);
        //     setGridSize(newGridSize);
        //     setShowOriginal(true);
        // } catch (error) {
        //     console.error('Voxelization failed', error);
        //     alert('Voxelization failed.');
        // }

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('unit', 'mm');
            formData.append('part', settings.brickType === 'plate' ? 'plate_1x1' : 'brick_1x1');
            formData.append('max_dim_limit', String(resolution));
            formData.append('default_color', String(settings.colorCode));
            formData.append('color_mode', 'none');

            const response = await fetch(`${API_BASE_URL}/api/process`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                let detail = 'Processing failed.';
                try {
                    const payload = await response.json();
                    if (payload?.detail) {
                        detail = payload.detail;
                    }
                } catch (jsonError) {
                    console.warn('Failed to parse error payload', jsonError);
                }
                throw new Error(detail);
            }

            const metadataHeader = response.headers.get('X-Legoizer-Metadata');
            if (metadataHeader) {
                try {
                    setReportMetadata(JSON.parse(metadataHeader));
                } catch (metadataError) {
                    console.warn('Failed to parse metadata header', metadataError);
                    setReportMetadata(null);
                }
            }

            // Read both text (to render) and blob (to download)
            const text = await response.clone().text();
            try {
                const bricks = parseMpdInstances(text);
                setMpdBricks(bricks);
                // Hide client-side voxel overlay in favor of MPD result
                setVoxels(bricks);
                setShowOriginal(true);
            } catch (parseErr) {
                console.warn('Failed to parse MPD content, falling back to client voxels', parseErr);
            }

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            setMpdDownloadUrl(objectUrl);

            const derivedFilename =
                parseFilenameFromContentDisposition(response.headers.get('Content-Disposition')) ||
                `${file.name.replace(/\.[^/.]+$/, '') || 'model'}.mpd`;
            setMpdFilename(derivedFilename);
        } catch (error) {
            console.error('Backend processing failed', error);
            const message = error instanceof Error ? error.message : 'Processing failed.';
            setApiError(message);
            alert(message);
        } finally {
            setIsProcessing(false);
            setIsDone(true);
        }
  };

    const triggerBlobDownload = (url: string, filename: string) => {
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
    };

  const handleExportLdr = () => {
        if (mpdDownloadUrl) {
            const filename =
                mpdFilename || `${aiAnalysis?.title || file?.name?.split('.')[0] || 'brickify_model'}.mpd`;
            triggerBlobDownload(mpdDownloadUrl, filename);
            return;
        }
    if (voxels.length === 0) return;
    // Converts strict JSON structure to LDraw
    const ldrContent = generateLDR(
        voxels, 
        settings.brickType,
        aiAnalysis?.title || file?.name.split('.')[0] || "model"
    );
    downloadFile(ldrContent, `${aiAnalysis?.title || "brickify_model"}.ldr`);
  };


  return (
    <div className="flex h-screen w-screen bg-neutral-900 text-neutral-200 font-sans overflow-hidden">
      {/* Sidebar Controls */}
      <div className="w-80 flex flex-col border-r border-neutral-800 bg-neutral-900 z-20 shadow-xl">
        <div className="p-6 border-b border-neutral-800">
          <h1 className="text-2xl font-bold flex items-center gap-2 text-yellow-500">
            <Box className="w-8 h-8" />
            Brickify 3D
          </h1>
          <p className="text-xs text-neutral-500 mt-1">OBJ &rarr; MPD</p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* File Upload */}
          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-4">1. Load Model</h2>
            <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-neutral-700 border-dashed rounded-lg cursor-pointer hover:bg-neutral-800 transition-colors">
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    <Upload className="w-6 h-6 mb-2 text-neutral-400" />
                    <p className="text-xs text-neutral-400">
                        {file ? file.name : "Upload .OBJ File"}
                    </p>
                </div>
                <input type="file" accept=".obj" className="hidden" onChange={handleFileChange} />
            </label>
          </section>


          {/* Voxel Settings */}
          <section>
            <div className="pt-4 border-t border-neutral-800 space-y-3">
             <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-4 flex items-center gap-2">
                {/* <Settings className="w-4 h-4" /> Config */}
                2. Config
             </h2>
             
                {/* Element Type */}
                <div>
                   <label className="block text-xs text-neutral-400 mb-2">Brick Type</label>
                   <div className="flex gap-2 p-1 bg-neutral-800 rounded-lg border border-neutral-700">
                        <button 
                            onClick={() => setSettings({...settings, brickType: 'brick'})}
                            className={`flex-1 py-1.5 text-xs rounded-md transition-all flex items-center justify-center gap-2 ${settings.brickType === 'brick' ? 'bg-neutral-700 text-white shadow-sm' : 'text-neutral-500 hover:text-neutral-300'}`}
                        >
                            <Box className="w-3 h-3" /> Brick
                        </button>
                        <button 
                            onClick={() => setSettings({...settings, brickType: 'plate'})}
                            className={`flex-1 py-1.5 text-xs rounded-md transition-all flex items-center justify-center gap-2 ${settings.brickType === 'plate' ? 'bg-neutral-700 text-white shadow-sm' : 'text-neutral-500 hover:text-neutral-300'}`}
                        >
                            <Layers className="w-3 h-3" /> Plate
                        </button>
                   </div>
                </div>

                <div>
                <label className="block text-slate-300 text-sm mb-2">
                    Longest Side Size (mm)
                    <span className="block text-xs text-slate-500 mt-0.5">Scale the vertex cloud to this size.</span>
                </label>
                <input 
                    type="number" 
                    min="100" 
                    max="10000" 
                    value={resolution}
                    onChange={(e) => {
                        const val = parseInt(e.target.value);
                        if (!isNaN(val)) setResolution(val);
                    }}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                />
                </div>

                {/* <div>
                    <label className="block text-xs text-neutral-400 mb-1">Resolution</label>
                    <input 
                        type="range" min="10" max="64" step="2"
                        value={settings.resolution}
                        onChange={(e) => setSettings({...settings, resolution: parseInt(e.target.value)})}
                        className="w-full h-2 bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-yellow-500"
                    />
                    <div className="flex justify-between text-xs mt-1">
                        <span className="text-neutral-500">10</span>
                        <span className="text-yellow-500 font-bold">{settings.resolution}</span>
                        <span className="text-neutral-500">64</span>
                    </div>
                </div>

                <div>
                    <label className="block text-xs text-neutral-400 mb-1">Color</label>
                    <div className="grid grid-cols-6 gap-2">
                        {LEGO_COLORS.map(c => (
                            <button
                                key={c.code}
                                onClick={() => setSettings({...settings, colorCode: c.code})}
                                className={`w-6 h-6 rounded-full border-2 transition-transform hover:scale-110 ${settings.colorCode === c.code ? 'border-white scale-110' : 'border-transparent'}`}
                                style={{ backgroundColor: c.hex }}
                                title={c.name}
                            />
                        ))}
                    </div>
                </div> */}
             </div>
          </section>

          {/* Actions */}
          <div className="pt-4 border-t border-neutral-800 space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-2">3. Process</h2>
            <button
                onClick={handleVoxelizeGeometric}
                disabled={!mesh || isProcessing}
                className="w-full py-3 bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 text-white rounded-lg font-bold flex items-center justify-center gap-2 transition-all"
            >
                {isProcessing ? <RefreshCw className="animate-spin w-4 h-4"/> : <Box className="w-4 h-4"/>}
                Voxelize Mesh
            </button>
          </div>

          {/* Scene Settings */}
           {/* <section>
             <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-4 flex items-center gap-2">
                <Sun className="w-4 h-4" /> Scene
             </h2>
             <div>
                <label className="block text-xs text-neutral-400 mb-1">Light Angle</label>
                <div className="flex items-center gap-2">
                    <input 
                        type="range" min="0" max="360"
                        value={lightRotation}
                        onChange={(e) => setLightRotation(parseInt(e.target.value))}
                        className="flex-1 h-2 bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-yellow-500"
                    />
                </div>
             </div>
          </section> */}

          {/* Export */}
            {isDone && (
                <div className="pt-4 border-t border-neutral-800 space-y-3">
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-2">4. Export</h2>

                    <div className="flex gap-2">
                        {/* <button
                            onClick={handleDownloadJson}
                            className="flex-1 py-2 bg-neutral-800 border border-neutral-700 hover:bg-neutral-700 text-neutral-300 rounded-lg text-sm flex items-center justify-center gap-2"
                        >
                            <FileJson className="w-4 h-4" /> JSON
                        </button> */}
                        <button
                            disabled={!mpdDownloadUrl && voxels.length === 0}
                            onClick={handleExportLdr}
                            className="flex-1 py-2 bg-yellow-500 hover:bg-yellow-400 text-black rounded-lg font-bold text-sm flex items-center justify-center gap-2"
                        >
                            {!mpdDownloadUrl && voxels.length === 0 ? <RefreshCw className="animate-spin w-4 h-4"/> : <Download className="w-4 h-4" />} MPD
                        </button>
                    </div>
                    {mpdDownloadUrl && (
                        <div className="text-xs text-neutral-500 bg-neutral-800 border border-neutral-700 rounded-md px-3 py-2">
                            <span className="text-green-400 font-semibold mr-2">MPD ready</span>
                            {brickCount !== null && (
                                <span className="mr-2">Bricks: {brickCount}</span>
                            )}
                            {voxelCount !== null && (
                                <span>Voxels: {voxelCount}</span>
                            )}
                        </div>
                    )}
                    {apiError && (
                        <div className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-md px-3 py-2">
                            {apiError}
                        </div>
                    )}
                </div>
            )}
        </div>
    </div>

      {/* Main Viewport */}
    <div className="flex-1 relative">
        <div className="absolute top-4 left-4 z-10 flex gap-4">
            <button
                onClick={() => setShowOriginal(!showOriginal)}
                className="bg-neutral-800/80 backdrop-blur text-white px-3 py-1.5 rounded-md text-sm flex items-center gap-2 border border-neutral-700 hover:bg-neutral-700"
            >
                {showOriginal ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                {showOriginal ? "Hide Original" : "Show Original"}
            </button>

            <div className="bg-neutral-800/80 backdrop-blur text-neutral-400 px-3 py-1.5 rounded-md text-sm border border-neutral-700">
                Voxels: {voxels.length}
            </div>

            <div className="">
                <label className="block text-xs text-neutral-400 mb-1">Light Angle</label>
                <div className="flex items-center gap-2">
                    <input
                        type="range" min="0" max="360"
                        value={lightRotation}
                        onChange={(e) => setLightRotation(parseInt(e.target.value))}
                        className="flex-1 h-2 bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-yellow-500"
                    />
                </div>
            </div>
        </div>

         <Viewer 
            ref={viewerRef}
            objFile={file} 
            voxels={voxels}
                mpdBricks={mpdBricks || undefined}
            gridSize={gridSize}
            showOriginal={showOriginal}
            brickType={settings.brickType}
            lightRotation={lightRotation}
            onMeshLoaded={setMesh}
            isLoading={isProcessing}
         />
      </div>
    </div>
  );
}