INSERT INTO sismos_dwh.dim_magnitude(magnitude_key, bucket, min_mag, max_mag, description) VALUES
(1, 'micro/menor', NULL, 2.9, 'Sismos de baja magnitud, normalmente poco perceptibles'),
(2, 'ligero', 3.0, 3.9, 'Sismos ligeros'),
(3, 'moderado', 4.0, 4.9, 'Sismos moderados'),
(4, 'fuerte', 5.0, 5.9, 'Sismos fuertes'),
(5, 'muy fuerte', 6.0, 6.9, 'Sismos muy fuertes'),
(6, 'mayor', 7.0, NULL, 'Sismos mayores')
ON CONFLICT (magnitude_key) DO NOTHING;
