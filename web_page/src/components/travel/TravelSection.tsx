import { useEffect, useMemo, useState } from 'react';
import { destinations, nextStop } from '@/content/siteContent';
import { Reveal } from '@/components/common/Reveal';
import { SectionHeader } from '@/components/common/SectionHeader';
import { AbstractMap } from './AbstractMap';
import { DestinationCard } from './DestinationCard';
import { NextStopBlock } from './NextStopBlock';
import { TravelFilters } from './TravelFilters';
import { TravelLog } from './TravelLog';
import { TravelStoryPanel } from './TravelStoryPanel';

const filters = ['全部', ...Array.from(new Set(destinations.map((destination) => destination.region)))];

export function TravelSection() {
  const [selectedFilter, setSelectedFilter] = useState('全部');
  const [activeCity, setActiveCity] = useState(destinations[0].city);
  const [expandedCity, setExpandedCity] = useState<string | null>(null);

  const filteredDestinations = useMemo(
    () => selectedFilter === '全部' ? destinations : destinations.filter((destination) => destination.region === selectedFilter),
    [selectedFilter],
  );

  const activeDestination = filteredDestinations.find((destination) => destination.city === activeCity) ?? filteredDestinations[0];

  useEffect(() => {
    if (!filteredDestinations.some((destination) => destination.city === activeCity)) {
      setActiveCity(filteredDestinations[0].city);
    }
  }, [activeCity, filteredDestinations]);

  const selectDestination = (city: string) => setActiveCity(city);
  const toggleExpanded = (city: string) => setExpandedCity((current) => current === city ? null : city);

  return (
    <section className="section travel-section" id="travel">
      <div className="section-inner">
        <Reveal>
          <SectionHeader eyebrow="02 / 旅行日志" title="地图之外。" intro="每座城市都有自己的频率。这里不是按国家收集的清单，而是一组仍在回响的坐标。" />
        </Reveal>
        <Reveal><TravelFilters filters={filters} selected={selectedFilter} onChange={setSelectedFilter} /></Reveal>
        <div className="travel-experience">
          <Reveal><AbstractMap destinations={filteredDestinations} activeCity={activeDestination.city} onSelect={selectDestination} /></Reveal>
          <Reveal><TravelStoryPanel destination={activeDestination} /></Reveal>
        </div>
        <Reveal><TravelLog destinations={filteredDestinations} activeCity={activeDestination.city} onSelect={selectDestination} /></Reveal>
        <div className="destination-list">
          {filteredDestinations.map((destination, index) => (
            <Reveal key={destination.city}>
              <DestinationCard destination={destination} index={index} isActive={activeDestination.city === destination.city} isExpanded={expandedCity === destination.city} onSelect={selectDestination} onToggleExpand={toggleExpanded} />
            </Reveal>
          ))}
        </div>
        <Reveal><NextStopBlock stop={nextStop} /></Reveal>
      </div>
    </section>
  );
}
