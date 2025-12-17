import { GoogleGenAI, Type } from "@google/genai";
import { AiAnalysis, VoxelData } from '../types';
import * as THREE from 'three';

const getAiClient = () => {
    const apiKey = process.env.API_KEY;
    if (!apiKey) throw new Error("API Key not found");
    return new GoogleGenAI({ apiKey });
};

export const analyzeModel = async (imageBase64: string): Promise<AiAnalysis> => {
  const ai = getAiClient();
  
  const cleanBase64 = imageBase64.replace(/^data:image\/(png|jpeg|jpg);base64,/, "");

  const prompt = `
    Analyze this voxelized 3D model (which looks like a Lego build).
    1. Give it a creative name suitable for a Lego set.
    2. Write a short, fun description (max 2 sentences).
    3. Suggest a Lego Theme (e.g., City, Star Wars, Architecture, Creator).
    4. Estimate a fun "piece count" based on the complexity you see.
  `;

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: {
        parts: [
            { inlineData: { mimeType: 'image/png', data: cleanBase64 } },
            { text: prompt }
        ]
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            title: { type: Type.STRING },
            description: { type: Type.STRING },
            theme: { type: Type.STRING },
            piecesCount: { type: Type.INTEGER }
          },
          required: ["title", "description", "theme", "piecesCount"]
        }
      }
    });

    if (response.text) {
        return JSON.parse(response.text) as AiAnalysis;
    }
    throw new Error("No response text");

  } catch (error) {
    console.error("AI Analysis failed:", error);
    return {
        title: "Mystery Build",
        description: "An awesome voxel creation.",
        theme: "Custom",
        piecesCount: 0
    };
  }
};

export const voxelizeWithAi = async (images: string[], resolution: number, colorCode: number): Promise<VoxelData[]> => {
    const ai = getAiClient();

    // Prepare image parts
    const parts = images.map(img => ({
        inlineData: {
            mimeType: 'image/jpeg',
            data: img.replace(/^data:image\/(png|jpeg|jpg);base64,/, "")
        }
    }));

    const prompt = `
        You are a 3D Voxel Engine.
        Analyze these 6 views (Front, Right, Back, Left, Top, Isometric) of a 3D object.
        Reconstruct the object as a SOLID 3D voxel grid of size ${resolution}x${resolution}x${resolution}.
        
        Rules:
        1. The output must be a JSON object containing a "voxels" array.
        2. Each voxel is { "x": number, "y": number, "z": number }.
        3. Coordinates x, y, z must be integers between 0 and ${resolution - 1}.
        4. Coordinate system: Y is UP.
        5. Ensure the object is SOLID (filled interior), not just a hollow shell.
        6. Do not miss the main features. Approximate the shape as best as possible within the ${resolution}x${resolution}x${resolution} grid.

        Output JSON only.
    `;

    try {
        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: {
                parts: [
                    ...parts,
                    { text: prompt }
                ]
            },
            config: {
                responseMimeType: "application/json",
                // We define a schema to ensure valid coordinates
                responseSchema: {
                    type: Type.OBJECT,
                    properties: {
                        voxels: {
                            type: Type.ARRAY,
                            items: {
                                type: Type.OBJECT,
                                properties: {
                                    x: { type: Type.INTEGER },
                                    y: { type: Type.INTEGER },
                                    z: { type: Type.INTEGER }
                                },
                                required: ["x", "y", "z"]
                            }
                        }
                    },
                    required: ["voxels"]
                }
            }
        });

        if (response.text) {
            const data = JSON.parse(response.text) as { voxels: {x:number, y:number, z:number}[] };
            
            // Map to VoxelData structure
            return data.voxels.map(v => ({
                position: new THREE.Vector3(v.x, v.y, v.z),
                colorIndex: colorCode
            }));
        }
        throw new Error("No response text from AI Voxelizer");

    } catch (e) {
        console.error("AI Voxelization Failed:", e);
        throw e;
    }
};