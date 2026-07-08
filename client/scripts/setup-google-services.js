#!/usr/bin/env node
// EAS Build hook to create google-services.json from environment variable

const fs = require('fs');
const path = require('path');

const base64Content = process.env.GOOGLE_SERVICES_JSON_BASE64;

if (!base64Content) {
  console.error('Error: GOOGLE_SERVICES_JSON_BASE64 environment variable is not set');
  process.exit(1);
}

try {
  console.log('Creating google-services.json from environment variable...');
  
  const jsonContent = Buffer.from(base64Content, 'base64').toString('utf-8');
  const outputPath = path.join(process.cwd(), 'google-services.json');
  
  fs.writeFileSync(outputPath, jsonContent);
  
  if (!fs.existsSync(outputPath)) {
    console.error('Error: Failed to create google-services.json');
    process.exit(1);
  }
  
  console.log('✓ google-services.json created successfully');
  process.exit(0);
} catch (error) {
  console.error('Error creating google-services.json:', error.message);
  process.exit(1);
}
