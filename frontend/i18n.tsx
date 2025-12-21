import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

type LanguageCode = 'zh' | 'en';

type TranslationDictionary = Record<string, string>;

type Translations = Record<LanguageCode, TranslationDictionary>;

const STORAGE_KEY = 'legoizer.language';

const translations: Translations = {
  zh: {
    'app.title': 'Brickify 3D',
    'app.subtitle': 'OBJ / .GLB 文件 → MPD',
    'sidebar.step1': '1. 导入模型',
    'sidebar.upload.placeholder': '上传 .OBJ / .GLB 文件',
    'sidebar.step2': '2. 参数配置',
    'sidebar.brickType': '砖块类型',
    'sidebar.brick': '砖块',
    'sidebar.plate': '薄片',
    'sidebar.longestSide': '最长边尺寸 (毫米)',
    'sidebar.longestSide.helper': '将顶点云缩放到该尺寸。',
    'sidebar.step3': '3. 开始处理',
    'sidebar.voxelize': '体素化模型',
    'sidebar.step4': '4. 导出',
    'sidebar.export.mpd': 'MPD 下载',
    'sidebar.export.ready': 'MPD 已生成',
    'sidebar.metrics.bricks': '砖块',
    'sidebar.metrics.voxels': '体素',
    'sidebar.error.processing': '生成失败。',
    'sidebar.error.alert': '处理失败。',
    'viewer.toggle.original': '原始模型',
    'viewer.toggle.generated': '生成结果',
    'viewer.lightAngle': '光源角度',
    'viewer.processing.title': 'Processing...',
    'viewer.processing.subtitle': '正在计算 3D 几何',
    'viewer.voxelCount': '体素数量',
    'language.switcher.label': '语言',
  },
  en: {
    'app.title': 'Brickify 3D',
    'app.subtitle': 'OBJ / .GLB → MPD',
    'sidebar.step1': '1. Load Model',
    'sidebar.upload.placeholder': 'Upload .OBJ / .GLB File',
    'sidebar.step2': '2. Configuration',
    'sidebar.brickType': 'Brick Type',
    'sidebar.brick': 'Brick',
    'sidebar.plate': 'Plate',
    'sidebar.longestSide': 'Longest Side Size (mm)',
    'sidebar.longestSide.helper': 'Scale the vertex cloud to this size.',
    'sidebar.step3': '3. Process',
    'sidebar.voxelize': 'Voxelize Mesh',
    'sidebar.step4': '4. Export',
    'sidebar.export.mpd': 'MPD',
    'sidebar.export.ready': 'MPD ready',
    'sidebar.metrics.bricks': 'Bricks',
    'sidebar.metrics.voxels': 'Voxels',
    'sidebar.error.processing': 'Processing failed.',
    'sidebar.error.alert': 'Processing failed.',
    'viewer.toggle.original': 'Original',
    'viewer.toggle.generated': 'Result',
    'viewer.lightAngle': 'Light Angle',
    'viewer.processing.title': 'Processing...',
    'viewer.processing.subtitle': 'Computing 3D Geometry',
    'viewer.voxelCount': 'Voxels',
    'language.switcher.label': 'Language',
  },
};

interface TranslationContextValue {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  t: (key: string) => string;
}

const TranslationContext = createContext<TranslationContextValue | undefined>(undefined);

export const TranslationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<LanguageCode>('zh');

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as LanguageCode | null;
    if (stored && (stored === 'zh' || stored === 'en')) {
      setLanguageState(stored);
    }
  }, []);

  const setLanguage = useCallback((lang: LanguageCode) => {
    setLanguageState(lang);
    localStorage.setItem(STORAGE_KEY, lang);
  }, []);

  const t = useCallback(
    (key: string) => {
      const dict = translations[language] ?? translations.zh;
      return dict[key] ?? key;
    },
    [language]
  );

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, setLanguage, t]
  );

  return <TranslationContext.Provider value={value}>{children}</TranslationContext.Provider>;
};

export const useTranslation = (): TranslationContextValue => {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error('useTranslation must be used within a TranslationProvider');
  }
  return context;
};

export const supportedLanguages: Array<{ code: LanguageCode; label: string }> = [
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'English' },
];
