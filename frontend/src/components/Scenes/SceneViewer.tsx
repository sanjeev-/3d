/**
 * 3D Scene Viewer using Three.js and React Three Fiber.
 */

import { useRef, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import type { SceneObject } from '../../types';

interface SceneViewerProps {
  objects: SceneObject[];
  onObjectSelect?: (object: SceneObject) => void;
}

function SceneObjectMesh({ obj, onClick }: { obj: SceneObject; onClick?: () => void }) {
  return (
    <mesh
      position={[obj.position_x, obj.position_y, obj.position_z]}
      rotation={[obj.rotation_x, obj.rotation_y, obj.rotation_z]}
      scale={[obj.scale_x, obj.scale_y, obj.scale_z]}
      onClick={onClick}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color={obj.object_type === 'CHARACTER' ? 'blue' : 'gray'} />
    </mesh>
  );
}

export function SceneViewer({ objects, onObjectSelect }: SceneViewerProps) {
  return (
    <div style={{ width: '100%', height: '600px' }}>
      <Canvas camera={{ position: [10, 10, 10], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />

        <Grid
          args={[10, 10]}
          cellSize={1}
          cellThickness={0.5}
          fadeDistance={30}
        />

        {objects.map((obj) => (
          <SceneObjectMesh
            key={obj.id}
            obj={obj}
            onClick={() => onObjectSelect?.(obj)}
          />
        ))}

        <OrbitControls />
      </Canvas>
    </div>
  );
}
