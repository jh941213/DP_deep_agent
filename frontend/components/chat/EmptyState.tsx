import { motion } from "framer-motion"

type EmptyStateProps = {
  onPreset: (value: string) => void
}

export default function EmptyState({ onPreset }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="flex h-full flex-col items-center justify-center text-center"
    >
      <div className="relative mb-6 flex items-center justify-center">
        <img
          src="/cart.png"
          alt="Shopping Cart Logo"
          className="relative h-72 w-72 object-contain"
        />
      </div>

      <h2 className="font-ypairing text-2xl font-semibold text-white mb-4 tracking-wide">
        안녕하세요, 직구 에이전트입니다.
      </h2>
      <div className="text-[15px] text-gray-300 mb-10 font-normal leading-8 whitespace-pre-line px-4">
        <span className="font-semibold text-blue-200">Kith, Everlane, Allbirds, Monos</span> 등
        <br />
        글로벌 브랜드의 상품 검색과 실시간 재고 확인,
        <br />
        그리고 복잡한 직구 절차까지 제가 모두 해결해 드릴 수 있습니다.
      </div>
      <div className="flex flex-col items-center gap-3 w-full max-w-lg mt-8">
        <p className="font-ypairing text-[10px] text-gray-500 mb-2 font-bold tracking-[0.2em] uppercase opacity-80">
          Or try asking
        </p>
        <button
          onClick={() => onPreset("Kith에서 New Balance 992 Sweet Caramel 25만원 이하 찾아줘")}
          className="font-ypairing group flex items-center gap-2 px-5 py-2.5 rounded-full border border-white/5 bg-white/5 hover:bg-white/10 hover:border-blue-500/30 hover:shadow-[0_0_15px_rgba(59,130,246,0.1)] transition-all duration-300 w-auto min-w-[280px] justify-center"
        >
          <span className="text-gray-400 group-hover:text-blue-100 transition-colors text-sm">
            "Kith에서 New Balance 992 Sweet Caramel 25만원 이하 찾아줘"
          </span>
        </button>
        <button
          onClick={() => onPreset("Monos Metro Sling 체크아웃 만들어줘")}
          className="font-ypairing group flex items-center gap-2 px-5 py-2.5 rounded-full border border-white/5 bg-white/5 hover:bg-white/10 hover:border-blue-500/30 hover:shadow-[0_0_15px_rgba(59,130,246,0.1)] transition-all duration-300 w-auto min-w-[280px] justify-center"
        >
          <span className="text-gray-400 group-hover:text-blue-100 transition-colors text-sm">
            "Monos Metro Sling 체크아웃 만들어줘"
          </span>
        </button>
        <button
          onClick={() => onPreset("Allbirds Wool Runner Weathered Brown 체크아웃 만들어줘")}
          className="font-ypairing group flex items-center gap-2 px-5 py-2.5 rounded-full border border-white/5 bg-white/5 hover:bg-white/10 hover:border-blue-500/30 hover:shadow-[0_0_15px_rgba(59,130,246,0.1)] transition-all duration-300 w-auto min-w-[280px] justify-center"
        >
          <span className="text-gray-400 group-hover:text-blue-100 transition-colors text-sm">
            "Allbirds Wool Runner Weathered Brown 체크아웃 만들어줘"
          </span>
        </button>
      </div>
    </motion.div>
  )
}
