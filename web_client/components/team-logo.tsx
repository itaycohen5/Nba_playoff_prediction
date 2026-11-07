'use client';
import Image from 'next/image';
import { useState } from 'react';
import brands from '@/lib/team-brands.json';
export type TeamBrand = {abbreviation:string; logo:string; city:string; nickname:string; color:string; seed:number};
export function teamBrand(name:string):TeamBrand|undefined {
  return (brands as Record<string,TeamBrand>)[name];
}
export function TeamLogo({name,className=''}:{name:string;className?:string}) {
  const brand=teamBrand(name),[failed,setFailed]=useState('');
  if(!brand||failed===brand.logo)return <span className={'team-logo team-logo-fallback '+className} aria-hidden="true">{brand?.abbreviation??'—'}</span>;
  return <Image unoptimized className={'team-logo '+className} src={brand.logo} width={56} height={56} alt="" aria-hidden="true" onError={()=>setFailed(brand.logo)}/>;
}
