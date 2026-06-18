INSERT INTO sismos_dwh.dim_region(region_name, country_scope, min_lat, max_lat, min_lon, max_lon) VALUES
('Noroeste de México', 'mexico', 22.0, 33.5, -118.5, -105.0),
('Occidente de México', 'mexico', 16.0, 23.5, -110.0, -101.0),
('Centro de México', 'mexico', 17.0, 22.5, -101.5, -96.0),
('Sur-Pacifico de México', 'mexico', 13.5, 18.5, -103.5, -92.0),
('Golfo y Sureste de México', 'mexico', 14.0, 22.5, -96.5, -86.0),
('Centroamérica', 'latam', 5.0, 18.5, -92.0, -77.0),
('Caribe', 'latam', 8.0, 24.0, -85.0, -59.0),
('Andes Norte', 'latam', -5.0, 13.0, -82.0, -66.0),
('Andes Centro', 'latam', -22.0, -5.0, -82.0, -62.0),
('Andes Sur', 'latam', -56.0, -22.0, -76.0, -53.0),
('Otra región', 'global', -90.0, 90.0, -180.0, 180.0)
ON CONFLICT (region_name) DO NOTHING;
