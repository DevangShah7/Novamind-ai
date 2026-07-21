import { useMemo, useRef } from 'react';
import { Canvas, useFrame, ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';

type Status = 'thinking' | 'complete' | 'idle';

interface ThinkingOrbSceneProps {
  status?: Status;
  size?: number;
  className?: string;
}

/* Status → color palette. Pure hues that read on both light + dark. */
const PALETTES: Record<Status, { a: string; b: string; c: string }> = {
  thinking: { a: '#7c3aed', b: '#06b6d4', c: '#ec4899' }, // purple / cyan / pink
  complete: { a: '#10b981', b: '#06b6d4', c: '#3b82f6' }, // green / cyan / blue
  idle:     { a: '#94a3b8', b: '#64748b', c: '#475569' }, // muted slate
};

/* Fibonacci-sphere distribution — even coverage without clustering. */
function fibonacciPoints(n: number, radius: number): Float32Array {
  const out = new Float32Array(n * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    out[i * 3 + 0] = Math.cos(theta) * r * radius;
    out[i * 3 + 1] = y * radius;
    out[i * 3 + 2] = Math.sin(theta) * r * radius;
  }
  return out;
}

interface ParticlesProps {
  status: Status;
  count: number;
}

function Particles({ status, count }: ParticlesProps) {
  const points = useRef<THREE.Points>(null);
  const positions = useMemo(() => fibonacciPoints(count, 1.4), [count]);
  const colors = useMemo(() => {
    const palette = PALETTES[status];
    const a = new THREE.Color(palette.a);
    const b = new THREE.Color(palette.b);
    const c = new THREE.Color(palette.c);
    const out = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const mix = i % 3 === 0 ? c : i % 2 === 0 ? a : b;
      out[i * 3 + 0] = mix.r;
      out[i * 3 + 1] = mix.g;
      out[i * 3 + 2] = mix.b;
    }
    return out;
  }, [count, status]);

  useFrame((_, delta) => {
    if (!points.current) return;
    // Status drives the speed: thinking is the most "alive".
    const speed = status === 'thinking' ? 0.25 : status === 'complete' ? 0.08 : 0.04;
    points.current.rotation.y += delta * speed;
    points.current.rotation.x += delta * speed * 0.2;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={count} array={colors} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial
        vertexColors
        size={0.018}
        sizeAttenuation
        transparent
        opacity={0.85}
        depthWrite={false}
      />
    </points>
  );
}

interface CoreProps {
  status: Status;
}

function Core({ status }: CoreProps) {
  const ref = useRef<THREE.Mesh>(null);
  const color = useMemo(() => new THREE.Color(PALETTES[status].a), [status]);

  useFrame((state) => {
    if (!ref.current) return;
    // Breathing: scale 0.95 → 1.05 on a sine wave. Faster when thinking.
    const t = state.clock.getElapsedTime();
    const speed = status === 'thinking' ? 1.6 : status === 'complete' ? 0.9 : 0.5;
    const s = 1 + Math.sin(t * speed) * 0.05;
    ref.current.scale.set(s, s, s);
  });

  return (
    <mesh ref={ref}>
      <icosahedronGeometry args={[0.45, 1]} />
      <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
    </mesh>
  );
}

function InnerEnergy({ status }: CoreProps) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => {
    if (!ref.current) return;
    const speed = status === 'thinking' ? 0.6 : 0.2;
    ref.current.rotation.x += delta * speed;
    ref.current.rotation.y += delta * speed * 0.8;
  });
  return (
    <mesh ref={ref}>
      <icosahedronGeometry args={[0.7, 0]} />
      <meshBasicMaterial color={PALETTES[status].b} wireframe transparent opacity={0.35} />
    </mesh>
  );
}

/**
 * The actual R3F scene. Kept separate from the wrapper so the
 * wrapper can be a `next/dynamic` import with `ssr: false` and a
 * CSS-only fallback during the brief lazy-load window.
 */
export default function ThinkingOrbScene({ status = 'thinking', size = 96, className }: ThinkingOrbSceneProps) {
  return (
    <div className={className} style={{ width: size, height: size, position: 'relative' }}>
      <Canvas
        camera={{ position: [0, 0, 3.2], fov: 45 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <ambientLight intensity={0.5} />
        <Particles status={status} count={1500} />
        <InnerEnergy status={status} />
        <Core status={status} />
      </Canvas>
    </div>
  );
}
